import argparse
import json
from pathlib import Path
import tempfile
import unittest
from test_gyazo import PNG
from grasp.sqlite_store import SQLiteStore, import_export_to_sqlite
from grasp.gyazo import ImageCache
from grasp.cards import run_cards, import_vt

A = 'a' * 32

class CardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.path = self.root / 'notes.sqlite'
        for project, pages in [
            ('notes', [{'id': 'same', 'title': 'One', 'lines': ['One', 'body 100% value', f'https://gyazo.com/{A}', '[/forest/Analysis]']}, {'id': 'plain', 'title': 'Plain', 'lines': ['Plain', 'plain body']}]),
            ('forest', [{'id': 'same', 'title': 'Analysis', 'lines': ['Analysis', f'https://gyazo.com/{A}', '[/notes/One]']}, {'id': 'twin', 'title': 'One', 'lines': ['One', 'not an explicit relation']}]),
        ]:
            f = self.root / (project + '.json'); f.write_text(json.dumps({'name': project, 'pages': pages}))
            import_export_to_sqlite(f, self.path, project_name=project)
        self.before = self.path.read_bytes(); self.store = SQLiteStore(self.path)
        self.cache = ImageCache(self.store); self.cache.scan(); self.cache.save_bytes(A, PNG, 'test')

    def tearDown(self):
        self.cache.close(); self.store.close()
        self.assertEqual(self.path.read_bytes(), self.before)
        self.tmp.cleanup()

    def cards(self, **kwargs):
        args = dict(limit=40, offset=0, query='', saved_only=False, page_id=None); args.update(kwargs)
        return run_cards(self.store, argparse.Namespace(**args))

    def test_page_identity_pagination_and_literal_query(self):
        page = self.cards(limit=1)
        self.assertEqual(page['total'], 4); self.assertEqual(page['next_offset'], 1)
        second = self.cards(limit=1, offset=1)
        self.assertNotEqual((page['items'][0]['project'], page['items'][0]['id']), (second['items'][0]['project'], second['items'][0]['id']))
        result = self.cards(saved_only=True)
        self.assertEqual({(p['project'], p['id']) for p in result['items']}, {('notes','same'),('forest','same')})
        self.assertEqual(self.cards(query='%')['total'], 1)
        self.assertEqual(self.cards(query="' OR 1=1 --")['total'], 0)
        self.assertTrue(all(p['image']['local_path'] for p in result['items']))
        with self.assertRaises(ValueError): self.cards(page_id='same')

    def test_cross_project_context_does_not_conflate_same_title(self):
        selected = SQLiteStore(self.path, project='notes')
        try:
            result = run_cards(selected, argparse.Namespace(limit=40, offset=0, query='', saved_only=False, page_id='same'))
        finally: selected.close()
        self.assertIn(('forest','same'), {(p['project'],p['id']) for p in result['outgoing']})
        self.assertIn(('forest','same'), {(p['project'],p['id']) for p in result['incoming']})
        self.assertEqual([(p['project'],p['id']) for p in result['same_title']], [('forest','twin')])
        self.assertEqual([(p['project'],p['id']) for p in result['shared_images']], [('forest','same')])

    def test_analysis_import_provenance_atomicity_and_structural_search(self):
        folder = self.root / 'vt'; folder.mkdir()
        catalog = folder / 'catalog-image-map-2026-08-03.json'
        desc = folder / 'structure-descriptions-2026-08-03.json'
        catalog.write_text(json.dumps([{'id': 1, 'page_ja': 'One', 'hash': A}]))
        desc.write_text(json.dumps([{'id': 'vt-001', 'formula': 'mediated fan-out'}]))
        history = folder / 'historical-ai-search-index-2026-08-13.json'
        history.write_text(json.dumps({'items': {A: {'page_ja': 'One', 'description': {'formula': 'different hypothesis'}, 'review': {'provenance': 'nishio', 'decision': 'accept'}}}}))
        before = {p.name:p.read_bytes() for p in folder.iterdir()}
        self.assertEqual(import_vt(self.cache, folder)['imported'], 2)
        self.assertEqual(self.cards(query='mediated fan-out')['total'], 2)
        records = [json.loads(r[0]) for r in self.cache.db.execute('SELECT body_json FROM image_analyses ORDER BY source_key')]
        self.assertEqual(records[0]['analysis_provenance'], 'AI'); self.assertIsNone(records[0]['review'])
        self.assertEqual(records[1]['review']['provenance'], 'nishio')
        self.assertEqual(before, {p.name:p.read_bytes() for p in folder.iterdir()})
        desc.write_text(json.dumps([{'id': 'vt-002', 'formula': 'wrong'}]))
        with self.assertRaises(ValueError): import_vt(self.cache, folder)
        self.assertEqual(self.cache.db.execute('SELECT COUNT(*) FROM image_analyses').fetchone()[0], 2)
