import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from grasp.gyazo import ImageCache, extract_urls, image_type, checked_url
from grasp.sqlite_store import SQLiteStore, import_export_to_sqlite

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5XcAAAAASUVORK5CYII=')
A = 'a' * 32
B = 'b' * 32


class GyazoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        export = self.root / 'notes.json'
        export.write_text(json.dumps({'name': 'notes', 'pages': [
            {'id': 'one', 'title': 'One', 'lines': ['One', f'[https://gyazo.com/{A}] https://i.gyazo.com/{B}.png', f'https://gyazo.com/{A}/raw']},
            {'id': 'two', 'title': 'Two', 'lines': ['Two', f'https://gyazo.com/{A}']},
        ]}))
        self.store_path = self.root / 'notes.sqlite'
        import_export_to_sqlite(export, self.store_path, project_name='notes')
        self.before = self.store_path.read_bytes()
        self.store = SQLiteStore(self.store_path, project='notes')
        self.cache = ImageCache(self.store)

    def tearDown(self):
        self.cache.close()
        self.store.close()
        self.assertEqual(self.before, self.store_path.read_bytes())
        self.temp.cleanup()

    def test_scan_reuse_idempotence_and_provenance(self):
        summary = self.cache.scan()
        self.assertEqual(summary['images'], 2)
        self.assertEqual(summary['references'], 4)
        self.assertEqual(self.cache.scan()['references'], 4)
        reuse = self.root / 'vt'; reuse.mkdir()
        (reuse / (A + '.img')).write_bytes(PNG)
        with patch('grasp.gyazo.download', side_effect=AssertionError('must stay offline')):
            self.assertEqual(self.cache.fetch([reuse], local_only=True)['reused'], 1)
            self.assertEqual(self.cache.fetch([reuse], local_only=True)['already_saved'], 1)
        record = self.cache.records(image_ids=[A])[0]
        self.assertEqual(len(record['references']), 3)
        self.assertTrue(record['origin'].startswith('local:'))
        self.assertEqual(Path(record['local_path']).read_bytes(), PNG)
        self.assertEqual(self.cache.records(page_id='two')[0]['image_id'], A)
        Path(record['local_path']).write_bytes(b'corrupt')
        self.assertEqual(self.cache.fetch([reuse], local_only=True)['reused'], 1)

    def test_failure_retry_limit_and_page_filter(self):
        self.cache.scan()
        unavailable = HTTPError('https://api.gyazo.com/', 503, 'unavailable', {}, None)
        with patch('grasp.gyazo.download', side_effect=unavailable):
            result = self.cache.fetch(limit=1, page_id='two')
        self.assertEqual(result['failed_this_run'], 1)
        self.assertEqual(result['states'], {'failed': 1, 'pending': 1})
        self.assertEqual(self.cache.records(image_ids=[A])[0]['error'], 'http_503')
        with patch('grasp.gyazo.download', return_value=PNG):
            self.assertEqual(self.cache.fetch(limit=1)['downloaded'], 1)  # direct B
        with patch('grasp.gyazo.download', side_effect=[json.dumps({'url': 'https://i.gyazo.com/' + A + '.png'}).encode(), PNG]):
            self.assertEqual(self.cache.fetch(retry_failed=True)['downloaded'], 1)
        self.assertEqual(self.cache.summary()['states'], {'saved': 2})

    def test_error_html_is_not_saved_and_unsafe_urls_are_blocked(self):
        self.cache.scan()
        with patch('grasp.gyazo.download', return_value=b'<html>temporarily unavailable</html>'):
            self.assertEqual(self.cache.fetch(image_ids=[B])['failed_this_run'], 1)
        self.assertIsNone(self.cache.records(image_ids=[B])[0]['local_path'])
        with patch('grasp.gyazo.download', return_value=b'[]'):
            self.assertEqual(self.cache.fetch(image_ids=[A])['failed_this_run'], 1)
        self.assertEqual(self.cache.records(image_ids=[A])[0]['error'], 'invalid_oembed_response')
        for code in (403, 404):
            with patch('grasp.gyazo.download', side_effect=HTTPError('https://api.gyazo.com/', code, 'unavailable', {}, None)):
                self.assertEqual(self.cache.fetch(image_ids=[A], retry_failed=True)['failed_this_run'], 1)
            self.assertEqual(self.cache.records(image_ids=[A])[0]['http_status'], code)
        for url in ['file:///etc/passwd', 'https://localhost/x', 'https://i.gyazo.com.evil.test/x', 'https://i.gyazo.com:8000/x', 'https://user@gyazo.com/x']:
            with self.assertRaises(ValueError): checked_url(url)
        with self.assertRaises(ValueError): image_type(b'<svg/>')
        self.assertEqual(extract_urls('https://gyazo.com/' + A + 'f'), [])
        self.assertEqual(extract_urls('https://gyazo.com.evil.test/' + A), [])


if __name__ == '__main__': unittest.main()
