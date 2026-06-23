import json
import tempfile
import unittest
from pathlib import Path

from grasp.cosense_cli import acquire_from_cosense, page_url_for_title, sync_from_cosense
from grasp.sqlite_store import SQLiteStore, ensure_store_schema, import_export_to_sqlite, parse_cosense_time


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


class FakeAcquireClient:
    def __init__(self):
        self.read_urls = []

    def search_full_text(self, project_url, query):
        self.project_url = project_url
        self.query = query
        return {
            "projectName": "remote",
            "count": 2,
            "pages": [
                {"id": "aaaaaaaaaaaaaaaaaaaaaaaa", "title": "A"},
                {"id": "bbbbbbbbbbbbbbbbbbbbbbbb", "title": "B"},
            ],
        }

    def list_pages(self, project_url, *, sort, limit, skip, filter_name=None):
        self.project_url = project_url
        self.sort = sort
        self.limit = limit
        self.skip = skip
        self.filter_name = filter_name
        return {
            "projectName": "remote",
            "count": 1,
            "pages": [
                {"id": "cccccccccccccccccccccccc", "title": "C"},
            ],
        }

    def read_page(self, page_url):
        self.read_urls.append(page_url)
        title = page_url.rsplit("/", 1)[-1]
        pages = {
            "A": {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A",
                "persistent": True,
                "created": "1970-01-01T09:00:01+09:00 (just now)",
                "updated": "1970-01-01T09:00:10+09:00 (just now)",
                "views": 100,
                "links": ["B"],
                "lines": [
                    {"text": "A", "created": "1970-01-01T09:00:01+09:00 (just now)", "updated": "1970-01-01T09:00:10+09:00 (just now)", "user": {"id": "u"}},
                    {"text": "links to [B]", "created": "1970-01-01T09:00:01+09:00 (just now)", "updated": "1970-01-01T09:00:10+09:00 (just now)", "user": {"id": "u"}},
                ],
            },
            "B": {
                "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                "title": "B",
                "persistent": True,
                "created": "1970-01-01T09:00:02+09:00 (just now)",
                "updated": "1970-01-01T09:00:20+09:00 (just now)",
                "views": 50,
                "links": ["Missing"],
                "lines": [
                    {"text": "B", "created": "1970-01-01T09:00:02+09:00 (just now)", "updated": "1970-01-01T09:00:20+09:00 (just now)", "user": {"id": "u"}},
                    {"text": "links to [Missing]", "created": "1970-01-01T09:00:02+09:00 (just now)", "updated": "1970-01-01T09:00:20+09:00 (just now)", "user": {"id": "u"}},
                ],
            },
            "C": {
                "id": "cccccccccccccccccccccccc",
                "title": "C",
                "persistent": True,
                "created": "1970-01-01T09:00:03+09:00 (just now)",
                "updated": "1970-01-01T09:00:30+09:00 (just now)",
                "views": 25,
                "links": [],
                "lines": [
                    {"text": "C", "created": "1970-01-01T09:00:03+09:00 (just now)", "updated": "1970-01-01T09:00:30+09:00 (just now)", "user": {"id": "u"}},
                ],
            },
        }
        return pages[title]


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
                self.assertEqual(store.unresolved_targets()[0]["title"], "D")
            finally:
                store.close()

    def test_acquire_search_creates_project_and_records_partial_coverage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            store = SQLiteStore(store_path)
            client = FakeAcquireClient()
            try:
                result = acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=client,
                    searches=["needle"],
                    limit=10,
                )

                self.assertEqual(result["project"], "remote:acquire")
                self.assertEqual(result["modes"], ["search"])
                self.assertEqual(result["coverage"], "partial")
                self.assertEqual(result["updated"], 2)
                self.assertEqual(client.read_urls, ["https://scrapbox.io/remote/A", "https://scrapbox.io/remote/B"])

                stats = store.stats()
                self.assertEqual(stats["pages"], 2)
                self.assertEqual(stats["acquisition"]["mode"], "search")
                self.assertEqual(stats["acquisition"]["coverage"], "partial")
                self.assertEqual(store.unresolved_targets()[0]["title"], "Missing")
            finally:
                store.close()

    def test_acquire_from_page_crawls_internal_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            store = SQLiteStore(store_path)
            client = FakeAcquireClient()
            try:
                result = acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=client,
                    project="remote:slice",
                    from_pages=["A"],
                    depth=1,
                    limit=10,
                )

                self.assertEqual(result["project"], "remote:slice")
                self.assertEqual(result["modes"], ["from-page"])
                self.assertEqual([page["title"] for page in result["pages"]], ["A", "B"])
                self.assertEqual(store.resolve_page("A").title, "A")
                self.assertEqual(store.resolve_page("B").title, "B")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
