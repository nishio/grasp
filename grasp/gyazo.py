"""Gyazo references and a resumable, local-only media cache owned by grasp.

The source note store is never modified. Cache metadata lives beside it.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

URL_RE = re.compile(r'https?://(?:i\.)?gyazo\.com/([0-9a-f]{32})(?:/raw|\.(?:png|jpe?g|gif|webp))?(?![0-9a-z_/-])', re.I)
ID_RE = re.compile(r'[0-9a-f]{32}')
MAX_BYTES = 25 * 1024 * 1024
ALLOWED_HOSTS = {'gyazo.com', 'i.gyazo.com', 'api.gyazo.com'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assets (
 image_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'pending', path TEXT,
 mime TEXT, sha256 TEXT, bytes INTEGER, origin TEXT, attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT, http_status INTEGER, checked_at REAL
);
CREATE TABLE IF NOT EXISTS refs (
 project TEXT, page_id TEXT, title TEXT, line_id TEXT, line_index INTEGER,
 url TEXT, image_id TEXT, PRIMARY KEY(project,page_id,line_id,url)
);
CREATE INDEX IF NOT EXISTS refs_image ON refs(image_id);
CREATE INDEX IF NOT EXISTS refs_page ON refs(project,page_id);
'''


def extract_urls(text):
    return [(m.group(1).lower(), m.group(0)) for m in URL_RE.finditer(text)]


def checked_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError('blocked_url')
    return url


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, timeout, max_bytes=MAX_BYTES):
    request = Request(checked_url(url), headers={'User-Agent': 'grasp-local-images/1.0', 'Accept': 'image/*,application/json'})
    with build_opener(SafeRedirect()).open(request, timeout=timeout) as response:
        checked_url(response.url)
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError('too_large')
        return data


def image_type(data):
    # Never accept HTML error pages, SVG, or unknown active document types.
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 33 and b'IEND' in data[-16:]:
        return 'png', 'image/png'
    if data.startswith(b'\xff\xd8\xff') and data.rstrip().endswith(b'\xff\xd9'):
        return 'jpg', 'image/jpeg'
    if data[:6] in (b'GIF87a', b'GIF89a') and len(data) > 13 and data[-1:] == b';':
        return 'gif', 'image/gif'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP' and len(data) >= 20:
        return 'webp', 'image/webp'
    raise ValueError('not_supported_image_or_error_page')


class ImageCache:
    def __init__(self, store, root=None):
        self.store = store
        self.root = Path(root or str(store.path) + '.assets').resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.root / 'index.sqlite', timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        owner = str(Path(store.path).resolve())
        row = self.db.execute("SELECT value FROM metadata WHERE key='source_store'").fetchone()
        if row and row[0] != owner:
            self.db.close()
            raise ValueError('cache belongs to another source store')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('source_store',?)", (owner,))
        self.db.commit()

    def close(self):
        self.db.close()

    def scan(self):
        project = self.store.project
        if project and project not in self.store.project_names():
            raise ValueError('project not found')
        query = '''SELECT l.project,l.page_id,p.title,l.line_id,l.line_index,l.text
                   FROM lines l JOIN pages p ON p.project=l.project AND p.id=l.page_id
                   WHERE lower(l.text) LIKE '%gyazo.com/%' '''
        params = []
        if project:
            query += 'AND l.project=?'
            params.append(project)
        count = 0
        with self.db:
            if project:
                self.db.execute('DELETE FROM refs WHERE project=?', (project,))
            else:
                self.db.execute('DELETE FROM refs')
            for row in self.store.connection.execute(query, params):
                for image_id, url in extract_urls(row['text']):
                    self.db.execute('INSERT OR IGNORE INTO assets(image_id) VALUES (?)', (image_id,))
                    self.db.execute('INSERT OR IGNORE INTO refs VALUES (?,?,?,?,?,?,?)',
                                    (row['project'], row['page_id'], row['title'], row['line_id'], row['line_index'], url, image_id))
                    count += 1
        return {**self.summary(), 'scan_matches': count}

    def filters(self, page_id=None, image_ids=None):
        where, params = ['a.image_id=r.image_id'], []
        if self.store.project:
            where.append('r.project=?')
            params.append(self.store.project)
        if page_id:
            where.append('r.page_id=?')
            params.append(page_id)
        if image_ids:
            if any(not ID_RE.fullmatch(value) for value in image_ids):
                raise ValueError('invalid image id')
            where.append('a.image_id IN (' + ','.join('?' for _ in image_ids) + ')')
            params.extend(image_ids)
        return ' AND '.join(where), params

    def records(self, page_id=None, image_ids=None, limit=50, offset=0):
        where, params = self.filters(page_id, image_ids)
        rows = self.db.execute(f'SELECT DISTINCT a.* FROM assets a JOIN refs r ON {where} ORDER BY a.image_id LIMIT ? OFFSET ?', [*params, limit, offset]).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            local = self.root / item['path'] if item['path'] else None
            if local and (not local.is_file() or not local.resolve().is_relative_to(self.root)):
                item['status'], item['error'] = 'missing', 'local_file_missing'
                local = None
            item['local_path'] = str(local) if local else None
            refs = 'SELECT project,page_id,title,line_id,line_index,url FROM refs WHERE image_id=?'
            ref_params = [item['image_id']]
            if self.store.project:
                refs += ' AND project=?'
                ref_params.append(self.store.project)
            item['references'] = [dict(r) for r in self.db.execute(refs + ' ORDER BY project,page_id,line_index', ref_params)]
            items.append(item)
        return items

    def summary(self):
        where, params = self.filters()
        counts = self.db.execute(f'SELECT status,COUNT(*) AS n FROM (SELECT DISTINCT a.image_id,a.status FROM assets a JOIN refs r ON {where}) GROUP BY status', params)
        states = {row['status']: row['n'] for row in counts}
        refs_where = ' WHERE project=?' if self.store.project else ''
        ref_params = [self.store.project] if self.store.project else []
        return {'cache_dir': str(self.root), 'project': self.store.project, 'images': sum(states.values()), 'states': states,
                'references': self.db.execute('SELECT COUNT(*) FROM refs' + refs_where, ref_params).fetchone()[0]}

    def save_bytes(self, image_id, data, origin):
        if len(data) > MAX_BYTES:
            raise ValueError('too_large')
        extension, mime = image_type(data)
        digest = hashlib.sha256(data).hexdigest()
        folder = self.root / 'files'
        folder.mkdir(exist_ok=True, mode=0o700)
        target = folder / f'{image_id}-{digest[:16]}.{extension}'
        fd, temporary = tempfile.mkstemp(dir=folder, prefix='.part-')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        with self.db:
            self.db.execute('UPDATE assets SET status=\'saved\',path=?,mime=?,sha256=?,bytes=?,origin=?,error=NULL,http_status=NULL,checked_at=? WHERE image_id=?',
                            (str(target.relative_to(self.root)), mime, digest, len(data), origin, time.time(), image_id))

    def fetch(self, reuse_dirs=(), image_ids=None, limit=50, local_only=False, retry_failed=False, timeout=5, page_id=None):
        where, params = self.filters(page_id=page_id, image_ids=image_ids)
        rows = self.db.execute(f'SELECT DISTINCT a.* FROM assets a JOIN refs r ON {where} ORDER BY a.image_id', params).fetchall()
        local = {}
        invalid_local = 0
        for directory in reuse_dirs:
            root = Path(directory).expanduser().resolve()
            if not root.is_dir():
                raise ValueError(f'reuse directory not found: {root}')
            for file in sorted(root.rglob('*')):
                if file.is_file() and ID_RE.fullmatch(file.stem.lower()) and file.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.img'}:
                    local.setdefault(file.stem.lower(), []).append(file)
        reused = fetched = attempted = skipped = failures = 0
        for row in rows:
            image_id = row['image_id']
            if row['status'] == 'saved' and row['path']:
                candidate = self.root / row['path']
                if candidate.is_file() and candidate.resolve().is_relative_to(self.root) and candidate.stat().st_size <= MAX_BYTES and hashlib.sha256(candidate.read_bytes()).hexdigest() == row['sha256']:
                    skipped += 1
                    continue
            success = False
            for file in local.get(image_id, []):
                try:
                    if file.stat().st_size > MAX_BYTES:
                        raise ValueError('too_large')
                    self.save_bytes(image_id, file.read_bytes(), 'local:' + str(file))
                    reused += 1
                    success = True
                    break
                except (OSError, ValueError):
                    invalid_local += 1
            if success or local_only or attempted >= limit or (row['status'] == 'failed' and not retry_failed):
                continue
            attempted += 1
            with self.db:
                self.db.execute('UPDATE assets SET attempts=attempts+1 WHERE image_id=?', (image_id,))
            urls = [r[0] for r in self.db.execute('SELECT DISTINCT url FROM refs WHERE image_id=?', (image_id,))]
            direct = next((url for url in urls if urlsplit(url).hostname == 'i.gyazo.com'), None)
            try:
                if direct:
                    url = 'https://' + direct.split('://', 1)[1]
                else:
                    metadata = json.loads(download('https://api.gyazo.com/api/oembed?' + urlencode({'url': 'https://gyazo.com/' + image_id}), timeout, 256_000))
                    if not isinstance(metadata, dict):
                        raise ValueError('invalid_oembed_response')
                    url = metadata.get('url')
                    if not isinstance(url, str):
                        raise ValueError('oembed_has_no_image_url')
                    if url.startswith('http://'):
                        url = 'https://' + url[7:]
                data = download(url, timeout)
                self.save_bytes(image_id, data, 'network:' + url)
                fetched += 1
            except (HTTPError, URLError, OSError, ValueError, TimeoutError) as error:
                status = error.code if isinstance(error, HTTPError) else None
                reason = f'http_{status}' if status else ('timeout' if isinstance(error, TimeoutError) else str(error)[:250])
                with self.db:
                    self.db.execute("UPDATE assets SET status='failed',error=?,http_status=?,checked_at=? WHERE image_id=?", (reason, status, time.time(), image_id))
                failures += 1
        return {**self.summary(), 'reused': reused, 'downloaded': fetched, 'attempted': attempted, 'failed_this_run': failures, 'already_saved': skipped, 'invalid_local_candidates': invalid_local}


def run_images(store, args):
    if args.limit < 0 or args.offset < 0 or not 0 < args.timeout <= 60:
        raise ValueError('limit/offset must be nonnegative; timeout must be 0..60 seconds')
    cache = ImageCache(store, args.cache_dir)
    try:
        if args.action == 'scan':
            return cache.scan()
        if args.action == 'fetch':
            return cache.fetch(args.reuse_dir, args.image_id, args.limit, args.local_only, args.retry_failed, args.timeout, args.page_id)
        if args.action == 'list':
            return {**cache.summary(), 'items': cache.records(args.page_id, args.image_id, args.limit, args.offset)}
        return cache.summary()
    finally:
        cache.close()
