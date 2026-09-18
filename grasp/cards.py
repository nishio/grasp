"""Read-only page cards and explicit connections over the grasp store and media cache."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
from .gyazo import ImageCache, ID_RE


def prepare(cache):
    cache.db.execute('CREATE TABLE IF NOT EXISTS image_analyses (image_id TEXT NOT NULL, source_key TEXT NOT NULL, body_json TEXT NOT NULL, PRIMARY KEY(image_id,source_key))')
    cache.db.commit()


def import_vt(cache, folder):
    folder = Path(folder).expanduser().resolve()
    if (folder / 'data').is_dir():
        folder = folder / 'data'
    def read(name):
        p = folder / name
        data = p.read_bytes()
        if len(data) > 25 * 1024 * 1024:
            raise ValueError('analysis file too large')
        return p, json.loads(data), hashlib.sha256(data).hexdigest()
    catalog_path, catalog, catalog_hash = read('catalog-image-map-2026-08-03.json')
    desc_path, descriptions, desc_hash = read('structure-descriptions-2026-08-03.json')
    if not isinstance(catalog, list) or not isinstance(descriptions, list):
        raise ValueError('invalid VT catalog/description format')
    def key(value):
        return int(str(value).removeprefix('vt-'))
    lookup = {}
    for row in descriptions:
        if not isinstance(row, dict) or 'id' not in row:
            raise ValueError('invalid VT description record')
        identity = key(row['id'])
        if identity in lookup:
            raise ValueError('duplicate VT description id')
        lookup[identity] = row
    entries = []
    for row in catalog:
        if not isinstance(row, dict) or not isinstance(row.get('page_ja'), str) or 'id' not in row or 'hash' not in row:
            raise ValueError('invalid VT catalog record')
        identity = key(row['id'])
        if identity not in lookup:
            raise ValueError(f'missing VT description: {identity}')
        entries.append((row['hash'], 'canonical:' + str(identity), {
            'title': row['page_ja'], 'vt_id': identity, 'analysis_provenance': 'AI',
            'description': lookup[identity], 'source_file': str(desc_path), 'source_sha256': desc_hash,
            'catalog_file': str(catalog_path), 'catalog_sha256': catalog_hash, 'tags': row.get('tags', []),
            'review': None, 'kind': 'canonical', 'catalog_entry': row,
            'image_provenance': row.get('image_provenance') or lookup[identity].get('image_provenance'),
        }))
    historical = folder / 'historical-ai-search-index-2026-08-13.json'
    if historical.exists():
        source, document, digest = read(historical.name)
        if not isinstance(document, dict) or not isinstance(document.get('items'), dict):
            raise ValueError('invalid historical analysis format')
        for image_id, row in document['items'].items():
            if not isinstance(row, dict):
                raise ValueError('invalid historical record')
            if not row.get('description'):
                continue
            if not isinstance(row['description'], dict) or (row.get('review') is not None and not isinstance(row['review'], dict)):
                raise ValueError('invalid historical description/review')
            entries.append((image_id, 'historical:' + image_id, {
                'title': row.get('page_ja', image_id), 'analysis_provenance': 'AI',
                'description': row['description'], 'source_file': str(source), 'source_sha256': digest,
                'review': row.get('review'), 'image_provenance': row.get('image_provenance'),
                'kind': 'search-index-only', 'status': row.get('status'),
            }))
    if any(not isinstance(image_id, str) or not ID_RE.fullmatch(image_id) for image_id, _, _ in entries):
        raise ValueError('invalid Gyazo hash in analysis data')
    if len({(i, s) for i, s, _ in entries}) != len(entries):
        raise ValueError('duplicate analysis identity')
    prepare(cache)
    # Validate all sources before replacing this explicitly selected snapshot.
    with cache.db:
        cache.db.execute('DELETE FROM image_analyses')
        cache.db.executemany('INSERT INTO image_analyses VALUES (?,?,?)', [(i, s, json.dumps(body, ensure_ascii=False)) for i, s, body in entries])
        cache.db.execute("INSERT OR REPLACE INTO metadata VALUES ('vt_data_dir',?)", (str(folder),))
    return {'imported': len(entries), 'images': len({i for i, _, _ in entries}), 'source': str(folder), 'provenance': 'AI descriptions; review provenance preserved separately'}


def lead(lines, title):
    text = '\n'.join(row['text'] for row in lines)
    text = re.sub(r'^---\n.*?\n---\n?', '', text, flags=re.S)
    return ' '.join(line.strip() for line in text.splitlines() if line.strip() and line.strip().lstrip('# ') != title)[:300]


def run_cards(store, args):
    if not 1 <= args.limit <= 100 or args.offset < 0:
        raise ValueError('cards limit must be 1..100 and offset nonnegative')
    cache = ImageCache(store)
    try:
        prepare(cache)
        cache.db.execute('ATTACH DATABASE ? AS notes', (Path(store.path).resolve().as_uri() + '?mode=ro',))
        if args.page_id:
            if not store.project:
                raise ValueError('cards --page-id requires --project to preserve identity')
            return context(cache, store.project, args.page_id)
        where, params = ['1=1'], []
        if store.project:
            where.append('p.project=?'); params.append(store.project)
        if args.saved_only:
            where.append("EXISTS (SELECT 1 FROM refs r JOIN assets a ON a.image_id=r.image_id WHERE r.project=p.project AND r.page_id=p.id AND a.status='saved')")
        if args.query:
            pattern = '%' + args.query.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
            where.append("""(p.title LIKE ? ESCAPE '!' OR EXISTS (SELECT 1 FROM notes.lines l WHERE l.project=p.project AND l.page_id=p.id AND l.text LIKE ? ESCAPE '!') OR EXISTS (SELECT 1 FROM refs r JOIN image_analyses a ON a.image_id=r.image_id WHERE r.project=p.project AND r.page_id=p.id AND a.body_json LIKE ? ESCAPE '!'))""")
            params.extend([pattern] * 3)
        where = ' AND '.join(where)
        total = cache.db.execute('SELECT COUNT(*) FROM notes.pages p WHERE ' + where, params).fetchone()[0]
        rows = cache.db.execute('SELECT p.* FROM notes.pages p WHERE ' + where + ' ORDER BY COALESCE(p.updated,0) DESC,p.project,p.id LIMIT ? OFFSET ?', [*params, args.limit, args.offset]).fetchall()
        cards = []
        for row in rows:
            project, page_id = row['project'], row['id']
            lines = cache.db.execute('SELECT text FROM notes.lines WHERE project=? AND page_id=? ORDER BY line_index LIMIT 30', (project, page_id)).fetchall()
            image = cache.db.execute("SELECT a.image_id FROM refs r JOIN assets a ON a.image_id=r.image_id WHERE r.project=? AND r.page_id=? ORDER BY (a.status='saved') DESC,r.line_index,a.image_id LIMIT 1", (project, page_id)).fetchone()
            media = cache.records(image_ids=[image[0]], limit=1) if image else []
            cards.append({'project': project, 'id': page_id, 'title': row['title'], 'snippet': lead(lines, row['title']), 'image': media[0] if media else None})
        return {'items': cards, 'total': total, 'offset': args.offset, 'limit': args.limit, 'next_offset': args.offset + len(cards) if args.offset + len(cards) < total else None}
    finally:
        cache.close()


def context(cache, project, page_id):
    page = cache.db.execute('SELECT * FROM notes.pages WHERE project=? AND id=?', (project, page_id)).fetchone()
    if not page:
        raise ValueError('page not found')
    def rows(sql, params):
        return [dict(row) for row in cache.db.execute(sql, params)]
    outgoing = rows("""SELECT DISTINCT p.project,p.id,p.title,'outgoing' AS relation FROM notes.edges e JOIN notes.pages p ON p.project=e.target_project AND p.id=e.target_page_id WHERE e.project=? AND e.source_page_id=? AND e.resolution_status='resolved_unique' AND e.connection_strength='strong' ORDER BY p.project,p.title,p.id LIMIT 101""", (project, page_id))
    incoming = rows("""SELECT DISTINCT p.project,p.id,p.title,'incoming' AS relation FROM notes.edges e JOIN notes.pages p ON p.project=e.project AND p.id=e.source_page_id WHERE e.target_project=? AND e.target_page_id=? AND e.resolution_status='resolved_unique' AND e.connection_strength='strong' ORDER BY p.project,p.title,p.id LIMIT 101""", (project, page_id))
    shared = rows('''SELECT DISTINCT p.project,p.id,p.title,r.image_id FROM refs mine JOIN refs r ON r.image_id=mine.image_id JOIN notes.pages p ON p.project=r.project AND p.id=r.page_id WHERE mine.project=? AND mine.page_id=? AND NOT (r.project=? AND r.page_id=?) ORDER BY p.project,p.title,p.id,r.image_id LIMIT 101''', (project, page_id, project, page_id))
    same = rows('SELECT project,id,title FROM notes.pages WHERE norm_title=? AND project<>? ORDER BY project,id LIMIT 101', (page['norm_title'], project))
    analyses = rows('SELECT DISTINCT a.image_id,a.source_key,a.body_json FROM refs r JOIN image_analyses a ON r.image_id=a.image_id WHERE r.project=? AND r.page_id=? ORDER BY a.image_id,a.source_key LIMIT 101', (project, page_id))
    result = {'project': project, 'id': page_id, 'outgoing': outgoing[:100], 'incoming': incoming[:100], 'shared_images': shared[:100], 'same_title': same[:100], 'analyses': [{**json.loads(r['body_json']), 'image_id': r['image_id'], 'source_key': r['source_key']} for r in analyses[:100]], 'truncated': any(len(v) > 100 for v in [outgoing, incoming, shared, same, analyses])}
    return result
