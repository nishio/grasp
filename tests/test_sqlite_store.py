import json
import tempfile
import unittest
from pathlib import Path

from grasp.sqlite_store import SQLiteStore, import_export_to_sqlite


FIXTURE = {
    "name": "fixture",
    "displayName": "fixture",
    "exported": 1,
    "users": [],
    "pages": [
        {
            "title": "A",
            "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "created": 1,
            "updated": 10,
            "views": 100,
            "lines": [
                {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                {"text": "links to [B] and [Missing]", "created": 1, "updated": 2, "userId": "u"},
            ],
        },
        {
            "title": "B",
            "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
            "created": 1,
            "updated": 20,
            "views": 50,
            "lines": [
                {"text": "B", "created": 1, "updated": 1, "userId": "u"},
                {"text": "links to [A]", "created": 1, "updated": 2, "userId": "u"},
            ],
        },
        {
            "title": "C",
            "id": "cccccccccccccccccccccccc",
            "created": 1,
            "updated": 30,
            "views": 10,
            "lines": [
                {"text": "C", "created": 1, "updated": 1, "userId": "u"},
                {"text": "also links to [B] and [Missing]", "created": 1, "updated": 2, "userId": "u"},
            ],
        },
    ],
}


class SQLiteStoreTests(unittest.TestCase):
    def test_import_export_to_sqlite_and_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")

            stats = import_export_to_sqlite(export_path, store_path)
            self.assertTrue(stats["schema_ok"])
            self.assertEqual(stats["pages"], 3)
            self.assertEqual(stats["lines"], 6)
            self.assertEqual(stats["edges"], 5)
            self.assertEqual(stats["wanted"], 1)

            store = SQLiteStore(store_path)
            try:
                page = store.resolve_page("a")
                self.assertIsNotNone(page)
                self.assertEqual(page.line_count, 2)
                self.assertTrue(store.schema_ok())

                lines, truncated = store.page_lines(page, limit=1)
                self.assertEqual([line.text for line in lines], ["A"])
                self.assertTrue(truncated)

                backlinks = store.backlinks("b")
                self.assertEqual([edge.source_title for edge in backlinks], ["A", "C"])

                hits = store.search("links", limit=2)
                self.assertEqual([hit["source_title"] for hit in hits], ["A", "B"])
                self.assertEqual(hits[0]["line_id"], "aaaaaaaaaaaaaaaaaaaaaaaa:1")

                wanted = store.wanted()
                self.assertEqual(wanted[0]["title"], "Missing")
                self.assertEqual(wanted[0]["count"], 2)

                existing_stats = store.link_stats("B")
                self.assertTrue(existing_stats["page_exists"])
                self.assertEqual(existing_stats["title"], "B")
                self.assertEqual(existing_stats["link_count"], 2)
                self.assertEqual(existing_stats["source_page_count"], 2)
                self.assertEqual(existing_stats["link_multiplicity"], "multi")

                missing_stats = store.link_stats("Missing")
                self.assertFalse(missing_stats["page_exists"])
                self.assertEqual(missing_stats["title"], "Missing")
                self.assertEqual(missing_stats["link_count"], 2)
                self.assertEqual(missing_stats["source_page_count"], 2)
                self.assertEqual(missing_stats["link_multiplicity"], "multi")

                absent_stats = store.link_stats("Nope")
                self.assertFalse(absent_stats["page_exists"])
                self.assertEqual(absent_stats["link_count"], 0)
                self.assertEqual(absent_stats["source_page_count"], 0)
                self.assertEqual(absent_stats["link_multiplicity"], "none")

                missing_related = store.related("Missing")
                self.assertEqual([item["title"] for item in missing_related], ["A", "C"])
                self.assertEqual(missing_related[0]["relation"], "backlink-source")
                self.assertEqual(missing_related[0]["score"], 1)

                read = store.read("A", backlink_limit=10, related_limit=10, wanted_limit=10)
                self.assertEqual(read["page"]["title"], "A")
                self.assertEqual(read["backlink_count_total"], 1)
                self.assertEqual(read["wanted"][0]["examples"][0]["source_title"], "A")

                missing_read = store.read("Missing", backlink_limit=10, related_limit=10, wanted_limit=10)
                self.assertIsNone(missing_read["page"])
                self.assertEqual(missing_read["backlink_count_total"], 2)
                self.assertEqual([item["title"] for item in missing_read["related"]], ["A", "C"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
