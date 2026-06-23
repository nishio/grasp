import json
import tempfile
import unittest
from pathlib import Path

from grasp.cosense_cli import page_url_for_title, sync_from_cosense
from grasp.sqlite_store import SQLiteStore, import_export_to_sqlite, parse_cosense_time


class FakeClient:
    def __init__(self):
        self.read_urls = []

    def list_pages(self, project_url, *, sort, limit, skip):
        self.project_url = project_url
        self.sort = sort
        self.limit = limit
        self.skip = skip
        return {
            "pages": [
                {
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "title": "A",
                    "updated": "1970-01-01T09:00:20+09:00 (just now)",
                    "pin": 0,
                },
                {
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "title": "B",
                    "updated": "1970-01-01T09:00:20+09:00 (just now)",
                    "pin": 0,
                },
            ]
        }

    def read_page(self, page_url):
        self.read_urls.append(page_url)
        return {
            "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "title": "A",
            "persistent": True,
            "created": "1970-01-01T09:00:01+09:00 (just now)",
            "updated": "1970-01-01T09:00:20+09:00 (just now)",
            "views": 101,
            "lines": [
                {
                    "text": "A",
                    "created": "1970-01-01T09:00:01+09:00 (just now)",
                    "updated": "1970-01-01T09:00:20+09:00 (just now)",
                    "user": {"id": "u"},
                },
                {
                    "text": "updated [D]",
                    "created": "1970-01-01T09:00:01+09:00 (just now)",
                    "updated": "1970-01-01T09:00:20+09:00 (just now)",
                    "user": {"id": "u"},
                },
            ],
        }


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
                {"text": "links to [Missing]", "created": 1, "updated": 2, "userId": "u"},
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
            ],
        },
    ],
}


class CosenseCliSyncTests(unittest.TestCase):
    def test_parse_cosense_time(self):
        self.assertEqual(parse_cosense_time("1970-01-01T09:00:20+09:00 (just now)"), 20)

    def test_page_url_for_title(self):
        self.assertEqual(page_url_for_title("https://scrapbox.io/nishio/", "A B"), "https://scrapbox.io/nishio/A%20B")

    def test_sync_upserts_changed_pages_until_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            client = FakeClient()
            try:
                result = sync_from_cosense(
                    store,
                    "https://scrapbox.io/nishio/",
                    client=client,
                    limit=10,
                )

                self.assertEqual(result["inspected"], 2)
                self.assertEqual(result["changed"], 1)
                self.assertEqual(result["updated"], 1)
                self.assertEqual(result["stopped_at"]["title"], "B")
                self.assertEqual(client.read_urls, ["https://scrapbox.io/nishio/A"])

                page = store.resolve_page("A")
                self.assertEqual(page.updated, 20)
                self.assertEqual(store.search("updated")[0]["source_title"], "A")
                self.assertEqual(store.backlinks("Missing"), [])
                self.assertEqual(store.wanted()[0]["title"], "D")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
