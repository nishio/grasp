import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import unquote

from grasp.cli import run_cross_project_acquire
from grasp.cosense_cli import (
    CosenseCliClient,
    CosenseCliError,
    acquire_from_cosense,
    classify_cosense_cli_failure,
    page_url_for_title,
    parse_cosense_page_url,
    refresh_page_from_cosense,
    sync_from_cosense,
)
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
                    "id": "hosted-line-a0",
                    "text": "A",
                    "created": "1970-01-01T09:00:01+09:00 (just now)",
                    "updated": "1970-01-01T09:00:20+09:00 (just now)",
                    "user": {"id": "u"},
                },
                {
                    "id": "hosted-line-a1",
                    "text": "updated [D]",
                    "created": "1970-01-01T09:00:01+09:00 (just now)",
                    "updated": "1970-01-01T09:00:20+09:00 (just now)",
                    "user": {"id": "u"},
                },
            ],
        }


class ExactPageClient:
    def __init__(self, page):
        self.page = page
        self.read_urls = []

    def read_page(self, page_url):
        self.read_urls.append(page_url)
        return self.page


class FullReconcileClient:
    def __init__(self):
        self.read_urls = []
        self.list_calls = []

    def list_pages(self, project_url, *, sort, limit, skip):
        self.list_calls.append({"sort": sort, "limit": limit, "skip": skip})
        pages = [
            {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A Renamed",
                "updated": "1970-01-01T09:00:10+09:00 (same)",
                "linesCount": 2,
                "pin": 0,
                "linked": 3,
                "views": 101,
            },
            {
                "id": "cccccccccccccccccccccccc",
                "title": "C",
                "updated": "1970-01-01T09:00:05+09:00 (old)",
                "linesCount": 1,
                "pin": 0,
                "linked": 1,
                "views": 25,
            },
        ]
        return {
            "projectName": "fixture",
            "count": 2,
            "pages": pages[skip : skip + limit],
        }

    def read_page(self, page_url):
        self.read_urls.append(page_url)
        title = unquote(page_url.rstrip("/").rsplit("/", 1)[-1])
        pages = {
            "A Renamed": {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A Renamed",
                "persistent": True,
                "created": "1970-01-01T09:00:01+09:00 (just now)",
                "updated": "1970-01-01T09:00:10+09:00 (same)",
                "views": 101,
                "lines": [
                    {
                        "id": "hosted-line-a0",
                        "text": "A Renamed",
                        "created": "1970-01-01T09:00:01+09:00 (just now)",
                        "updated": "1970-01-01T09:00:10+09:00 (same)",
                        "user": {"id": "u"},
                    },
                    {
                        "id": "hosted-line-a1",
                        "text": "still links to [Missing]",
                        "created": "1970-01-01T09:00:01+09:00 (just now)",
                        "updated": "1970-01-01T09:00:10+09:00 (same)",
                        "user": {"id": "u"},
                    },
                ],
            },
            "C": {
                "id": "cccccccccccccccccccccccc",
                "title": "C",
                "persistent": True,
                "created": "1970-01-01T09:00:03+09:00 (just now)",
                "updated": "1970-01-01T09:00:05+09:00 (old)",
                "views": 25,
                "lines": [
                    {
                        "id": "hosted-line-c0",
                        "text": "C",
                        "created": "1970-01-01T09:00:03+09:00 (just now)",
                        "updated": "1970-01-01T09:00:05+09:00 (old)",
                        "user": {"id": "u"},
                    },
                ],
            },
        }
        return pages[title]


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


class ReusableListAcquireClient(FakeAcquireClient):
    def __init__(self):
        self.read_urls = []

    def list_pages(self, project_url, *, sort, limit, skip, filter_name=None):
        self.project_url = project_url
        self.sort = sort
        self.limit = limit
        self.skip = skip
        self.filter_name = filter_name
        pages = [
            {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A",
                "updated": "1970-01-01T09:00:10+09:00 (just now)",
                "pin": 0,
            },
            {
                "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                "title": "B",
                "updated": "1970-01-01T09:00:20+09:00 (just now)",
                "pin": 0,
            },
        ]
        return {
            "projectName": "remote",
            "count": 2,
            "pages": pages[skip : skip + limit],
        }

    def read_page(self, page_url):
        page = super().read_page(page_url)
        for index, line in enumerate(page["lines"]):
            line["id"] = f"hosted-{page['title'].lower()}-{index}"
        return page


class FailingAcquireClient:
    def read_page(self, page_url):
        raise CosenseCliError(
            command=["cosense", "readPage", page_url],
            error_class="command-env",
            message="cosense CLI command failed",
            returncode=127,
            stderr="/usr/bin/env: node: No such file or directory",
        )

    def search_full_text(self, project_url, query):
        return {"projectName": "remote", "count": 0, "pages": []}

    def list_pages(self, project_url, *, sort, limit, skip, filter_name=None):
        return {"projectName": "remote", "count": 0, "pages": []}


class NonpersistentAcquireClient(FakeAcquireClient):
    def read_page(self, page_url):
        page = super().read_page(page_url)
        if page["title"] == "A":
            return {**page, "persistent": False}
        return page


class CrossProjectAcquireClient:
    def __init__(self):
        self.read_urls = []

    def read_page(self, page_url):
        self.read_urls.append(page_url)
        title = unquote(page_url.rstrip("/").rsplit("/", 1)[-1])
        page_ids = {
            "PageA": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "PageB": "bbbbbbbbbbbbbbbbbbbbbbbb",
        }
        link_line = {
            "PageA": "links [Shared] [/nishio/Origin]",
            "PageB": "links [Shared] [Other] [/nishio/Another]",
        }[title]
        return {
            "id": page_ids[title],
            "title": title,
            "persistent": True,
            "created": "1970-01-01T09:00:01+09:00 (just now)",
            "updated": "1970-01-01T09:00:10+09:00 (just now)",
            "views": 10,
            "links": [],
            "lines": [
                {"text": title, "created": "1970-01-01T09:00:01+09:00 (just now)", "updated": "1970-01-01T09:00:10+09:00 (just now)", "user": {"id": "u"}},
                {"text": link_line, "created": "1970-01-01T09:00:01+09:00 (just now)", "updated": "1970-01-01T09:00:10+09:00 (just now)", "user": {"id": "u"}},
            ],
        }

    def search_full_text(self, project_url, query):
        return {"projectName": "remote", "count": 0, "pages": []}

    def list_pages(self, project_url, *, sort, limit, skip, filter_name=None):
        return {"projectName": "remote", "count": 0, "pages": []}


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

    def test_parse_cosense_page_url_strips_query_and_preserves_fragment(self):
        result = parse_cosense_page_url("https://scrapbox.io/nishio/A%20B?x=1#hosted-line")
        self.assertEqual(result["project_url"], "https://scrapbox.io/nishio/")
        self.assertEqual(result["page_url"], "https://scrapbox.io/nishio/A%20B")
        self.assertEqual(result["title"], "A B")
        self.assertEqual(result["fragment"], "hosted-line")

    def test_parse_cosense_page_url_rejects_untrusted_origin(self):
        for page_url in (
            "https://example.com/nishio/A",
            "https://scrapbox.io.example.com/nishio/A",
            "https://attacker@scrapbox.io/nishio/A",
            "http://scrapbox.io/nishio/A",
            "https://scrapbox.io:8443/nishio/A",
        ):
            with self.subTest(page_url=page_url):
                with self.assertRaisesRegex(ValueError, "origin must be https://scrapbox.io"):
                    parse_cosense_page_url(page_url)

    def test_refresh_page_upserts_exact_newer_page_and_requests_reread(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            client = ExactPageClient(FakeClient().read_page("ignored"))

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A#hosted-line-a1",
                    client=client,
                )

                self.assertEqual(client.read_urls, ["https://scrapbox.io/fixture/A"])
                self.assertEqual(result["action"], "upserted")
                self.assertEqual(result["updated"], 1)
                self.assertTrue(result["store_current"])
                self.assertEqual(result["fragment"], "hosted-line-a1")
                self.assertTrue(result["read_after_refresh"]["required"])
                self.assertEqual(result["read_after_refresh"]["args"][-2:], ["--page-id", "aaaaaaaaaaaaaaaaaaaaaaaa"])
                self.assertEqual(store.search("updated")[0]["source_title"], "A")

                second = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=client,
                )
                self.assertEqual(second["action"], "cache-hit")
                self.assertEqual(second["updated"], 0)
                self.assertFalse(second["read_after_refresh"]["required"])
            finally:
                store.close()

    def test_refresh_page_same_timestamp_content_change_is_not_a_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A",
                "persistent": True,
                "created": 1,
                "updated": 10,
                "views": 100,
                "lines": [
                    {"id": "hosted-a0", "text": "A", "created": 1, "updated": 1, "user": {"id": "u"}},
                    {"id": "hosted-a1", "text": "changed in the same second", "created": 1, "updated": 10, "user": {"id": "u"}},
                ],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "upserted")
                self.assertIn("content_changed", result["reasons"])
                self.assertEqual(store.search("same second")[0]["source_title"], "A")
            finally:
                store.close()

    def test_refresh_page_accepts_local_seconds_within_remote_minute_precision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            fixture = json.loads(json.dumps(FIXTURE))
            fixture["pages"][0]["updated"] = 47
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A",
                "persistent": True,
                "created": "1970-01-01T09:00+09:00 (same minute)",
                "updated": "1970-01-01T09:00+09:00 (same minute)",
                "views": 100,
                "lines": [
                    {"text": "A", "created": 1, "updated": 1, "user": {"id": "u"}},
                    {"text": "links to [Missing]", "created": 1, "updated": 2, "user": {"id": "u"}},
                ],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "cache-hit")
                self.assertEqual(result["page_freshness"], "verified")
                self.assertEqual(result["remote"]["updated_precision_seconds"], 60)
                self.assertEqual(store.resolve_page("A").updated, 47)

                remote_page["lines"][1]["text"] = "changed within the same hosted minute"
                changed_result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=ExactPageClient(remote_page),
                )
                self.assertEqual(changed_result["action"], "upserted")
                self.assertIn("content_changed", changed_result["reasons"])
                self.assertEqual(store.search("same hosted minute")[0]["source_title"], "A")
            finally:
                store.close()

    def test_refresh_page_line_id_enrichment_preserves_more_precise_local_updated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            fixture = json.loads(json.dumps(FIXTURE))
            fixture["pages"][0]["updated"] = 47
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A",
                "persistent": True,
                "created": "1970-01-01T09:00+09:00 (same minute)",
                "updated": "1970-01-01T09:00+09:00 (same minute)",
                "views": 100,
                "lines": [
                    {"id": "hosted-a-0", "text": "A", "created": 1, "updated": 1, "user": {"id": "u"}},
                    {"id": "hosted-a-1", "text": "links to [Missing]", "created": 1, "updated": 2, "user": {"id": "u"}},
                ],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "upserted")
                self.assertEqual(result["reasons"], ["hosted_line_ids_missing"])
                page = store.resolve_page("A")
                self.assertEqual(page.updated, 47)
                lines, _ = store.page_lines(page)
                self.assertEqual([line.external_line_id for line in lines], ["hosted-a-0", "hosted-a-1"])
            finally:
                store.close()

    def test_refresh_page_keeps_definite_local_newer_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            fixture = json.loads(json.dumps(FIXTURE))
            fixture["pages"][0]["updated"] = 60
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "A",
                "persistent": True,
                "created": "1970-01-01T09:00+09:00 (older minute)",
                "updated": "1970-01-01T09:00+09:00 (older minute)",
                "views": 100,
                "lines": [
                    {"text": "A", "created": 1, "updated": 1, "user": {"id": "u"}},
                    {"text": "remote differs", "created": 1, "updated": 2, "user": {"id": "u"}},
                ],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "local-newer-conflict")
                self.assertEqual(result["page_freshness"], "conflict")
                self.assertEqual(store.search("remote differs"), [])
            finally:
                store.close()

    def test_refresh_page_dry_run_does_not_mutate_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            client = ExactPageClient(FakeClient().read_page("ignored"))

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=client,
                    dry_run=True,
                )

                self.assertEqual(result["action"], "would-upsert")
                self.assertEqual(result["updated"], 0)
                self.assertFalse(result["store_current"])
                self.assertEqual(store.resolve_page("A").updated, 10)
                self.assertEqual(store.search("updated"), [])
            finally:
                store.close()

    def test_refresh_page_refuses_to_expand_partial_acquisition_namespace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            store = SQLiteStore(store_path, for_write=True)
            try:
                acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=FakeAcquireClient(),
                    project="remote:slice",
                    searches=["needle"],
                    limit=10,
                )
                remote_c = FakeAcquireClient().read_page("https://scrapbox.io/remote/C")
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/remote/C",
                    client=ExactPageClient(remote_c),
                )

                self.assertFalse(result["refresh_allowed"])
                self.assertEqual(result["action"], "blocked")
                self.assertEqual(result["diagnostic"]["type"], "partial_acquisition_page_missing")
                self.assertIsNone(store.resolve_page("C"))
            finally:
                store.close()

    def test_refresh_page_refuses_unverified_cross_project_insert(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "cccccccccccccccccccccccc",
                "title": "C",
                "persistent": True,
                "created": 1,
                "updated": 30,
                "lines": [{"text": "C"}],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/another-project/C",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "blocked")
                self.assertEqual(result["diagnostic"]["type"], "project_identity_unverified")
                self.assertIsNone(store.resolve_page("C"))
            finally:
                store.close()

    def test_refresh_page_refuses_same_title_with_different_page_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "cccccccccccccccccccccccc",
                "title": "A",
                "persistent": True,
                "created": 1,
                "updated": 30,
                "lines": [{"text": "A recreated"}],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/A",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "blocked")
                self.assertEqual(result["diagnostic"]["type"], "page_identity_conflict")
                self.assertEqual(store.resolve_page("A").id, "aaaaaaaaaaaaaaaaaaaaaaaa")
            finally:
                store.close()

    def test_refresh_page_refuses_rename_onto_another_local_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "title": "B",
                "persistent": True,
                "created": 1,
                "updated": 30,
                "lines": [{"text": "A renamed to B"}],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/B",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "blocked")
                self.assertEqual(result["diagnostic"]["type"], "page_identity_conflict")
                self.assertEqual(store.resolve_page("A").id, "aaaaaaaaaaaaaaaaaaaaaaaa")
                self.assertEqual(store.resolve_page("B").id, "bbbbbbbbbbbbbbbbbbbbbbbb")
            finally:
                store.close()

    def test_refresh_page_returns_diagnostic_for_nonpersistent_page_without_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "title": "Transient",
                "persistent": False,
                "lines": [{"text": "Transient"}],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                result = refresh_page_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/Transient",
                    client=ExactPageClient(remote_page),
                )

                self.assertEqual(result["action"], "blocked")
                self.assertEqual(result["diagnostic"]["type"], "nonpersistent_page")
                self.assertEqual(result["remote"]["id"], "")
                self.assertIsNone(store.resolve_page("Transient"))
            finally:
                store.close()

    def test_refresh_page_rejects_persistent_response_without_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            remote_page = {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "persistent": True,
                "updated": 30,
                "lines": [{"text": "malformed"}],
            }

            store = SQLiteStore(store_path, project="fixture", for_write=True)
            try:
                with self.assertRaisesRegex(ValueError, "must include title"):
                    refresh_page_from_cosense(
                        store,
                        "https://scrapbox.io/fixture/A",
                        client=ExactPageClient(remote_page),
                    )
            finally:
                store.close()

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
                lines, _truncated = store.page_lines(page)
                self.assertEqual([line.line_id for line in lines], ["aaaaaaaaaaaaaaaaaaaaaaaa:0", "aaaaaaaaaaaaaaaaaaaaaaaa:1"])
                self.assertEqual([line.external_line_id for line in lines], ["hosted-line-a0", "hosted-line-a1"])
                self.assertEqual(lines[1].to_dict()["external_line_id"], "hosted-line-a1")
                self.assertTrue(result["line_id_policy"]["hosted_line_id_persisted"])
            finally:
                store.close()

    def test_full_reconcile_fetches_missing_renames_and_tombstones_deleted_pages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path, project="fixture")
            client = FullReconcileClient()
            try:
                result = sync_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/",
                    client=client,
                    batch_size=1,
                    full_reconcile=True,
                )

                self.assertEqual(result["mode"], "full-reconcile")
                self.assertEqual(result["inspected"], 2)
                self.assertEqual(result["manifest_count"], 2)
                self.assertEqual(result["changed"], 2)
                self.assertEqual(result["updated"], 2)
                self.assertEqual(result["missing_local"], 1)
                self.assertEqual(result["renamed"], 1)
                self.assertEqual(result["deleted"], 1)
                self.assertEqual(result["hosted_line_ids_seen"], 3)
                self.assertTrue(result["line_id_policy"]["hosted_line_id_persisted"])
                self.assertEqual(
                    client.read_urls,
                    ["https://scrapbox.io/fixture/A%20Renamed", "https://scrapbox.io/fixture/C"],
                )

                renamed = store.resolve_page("A Renamed")
                self.assertIsNotNone(renamed)
                self.assertEqual(renamed.id, "aaaaaaaaaaaaaaaaaaaaaaaa")
                self.assertEqual(store.resolve_page("A").id, "aaaaaaaaaaaaaaaaaaaaaaaa")
                self.assertIsNone(store.resolve_page("B"))
                self.assertEqual(store.resolve_page("C").id, "cccccccccccccccccccccccc")

                lines, _ = store.page_lines(renamed)
                self.assertEqual([line.line_id for line in lines], ["aaaaaaaaaaaaaaaaaaaaaaaa:0", "aaaaaaaaaaaaaaaaaaaaaaaa:1"])
                self.assertEqual([line.external_line_id for line in lines], ["hosted-line-a0", "hosted-line-a1"])
                tombstones = store.project_sync_tombstones()
                self.assertIn("bbbbbbbbbbbbbbbbbbbbbbbb", tombstones)
                self.assertEqual(tombstones["bbbbbbbbbbbbbbbbbbbbbbbb"]["title"], "B")
                self.assertEqual(store.stats()["pages"], 2)
                self.assertTrue(result["line_id_policy"]["hosted_line_id_persisted"])
            finally:
                store.close()

    def test_full_reconcile_dry_run_does_not_mutate_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path, project="fixture")
            client = FullReconcileClient()
            try:
                result = sync_from_cosense(
                    store,
                    "https://scrapbox.io/fixture/",
                    client=client,
                    batch_size=2,
                    dry_run=True,
                    full_reconcile=True,
                )

                self.assertEqual(result["changed"], 2)
                self.assertEqual(result["updated"], 0)
                self.assertEqual(result["deleted"], 1)
                self.assertEqual(client.read_urls, [])
                self.assertEqual(store.resolve_page("A").title, "A")
                self.assertEqual(store.resolve_page("B").title, "B")
                self.assertEqual(store.project_sync_tombstones(), {})
            finally:
                store.close()

    def test_sync_refuses_partial_acquisition_namespace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            store = SQLiteStore(store_path)
            acquire_client = FakeAcquireClient()
            try:
                acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=acquire_client,
                    project="remote:slice",
                    searches=["needle"],
                    limit=10,
                )
                result = sync_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=FullReconcileClient(),
                    full_reconcile=True,
                )

                self.assertFalse(result["sync_allowed"])
                self.assertEqual(result["diagnostic"]["type"], "partial_acquisition_not_syncable")
                self.assertEqual(result["inspected"], 0)
                self.assertEqual(result["changed"], 0)
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

    def test_acquire_reuses_unchanged_pages_for_same_updated_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            store = SQLiteStore(store_path)
            client = ReusableListAcquireClient()
            try:
                first = acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=client,
                    full_list=True,
                    limit=2,
                )

                self.assertEqual(first["fetched"], 2)
                self.assertEqual(first["updated"], 2)
                self.assertEqual(first["reused"], 0)
                self.assertFalse(first["same_criteria_as_previous"])
                self.assertEqual(client.read_urls, ["https://scrapbox.io/remote/A", "https://scrapbox.io/remote/B"])
                stats = store.stats()
                self.assertEqual(stats["acquisition"]["criteria_fingerprint"], first["criteria_fingerprint"])
                self.assertEqual(stats["acquisition"]["candidate_window"]["updated_range"]["oldest_epoch"], 10)
                self.assertIn("a", stats["acquisition"]["page_manifest"])

                client.read_urls.clear()
                second = acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=client,
                    full_list=True,
                    limit=2,
                )

                self.assertEqual(second["fetched"], 2)
                self.assertEqual(second["updated"], 0)
                self.assertEqual(second["remote_fetched"], 0)
                self.assertEqual(second["reused"], 2)
                self.assertTrue(second["same_criteria_as_previous"])
                self.assertEqual(client.read_urls, [])
                self.assertTrue(all(page["reused"] for page in second["pages"]))
                self.assertEqual(store.resolve_page("A").updated, 10)
                self.assertEqual(store.resolve_page("B").updated, 20)
                page_a = store.resolve_page("A")
                lines, _ = store.page_lines(page_a)
                self.assertEqual(
                    [line.external_line_id for line in lines],
                    ["hosted-a-0", "hosted-a-1"],
                )
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

    def test_acquire_all_failed_returns_diagnostic_and_error_classes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            store = SQLiteStore(store_path)
            client = FailingAcquireClient()
            try:
                result = acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=client,
                    project="remote:semantic",
                    seed_titles=["A", "B"],
                    limit=10,
                )

                self.assertEqual(result["fetched"], 0)
                self.assertEqual(result["updated"], 0)
                self.assertEqual(result["diagnostic"]["type"], "all_failed")
                self.assertEqual(result["diagnostic"]["error_classes"], {"command-env": 2})
                self.assertIn("node is on PATH", result["diagnostic"]["next_actions"][0])
                self.assertEqual(result["failed_pages"][0]["error_class"], "command-env")
                self.assertEqual(result["failed_pages"][0]["returncode"], 127)
                self.assertIn("node", result["failed_pages"][0]["stderr"])

                stats = store.stats()
                self.assertEqual(stats["pages"], 0)
                self.assertEqual(stats["acquisition"]["diagnostic_type"], "all_failed")
                self.assertEqual(stats["acquisition"]["error_classes"], {"command-env": 2})
            finally:
                store.close()

    def test_acquire_partial_nonpersistent_diagnostic_is_not_fetch_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            store = SQLiteStore(store_path)
            client = NonpersistentAcquireClient()
            try:
                result = acquire_from_cosense(
                    store,
                    "https://scrapbox.io/remote/",
                    client=client,
                    searches=["needle"],
                    limit=10,
                )

                self.assertEqual(result["fetched"], 1)
                self.assertEqual([page["title"] for page in result["pages"]], ["B"])
                self.assertEqual(result["diagnostic"]["type"], "partial_nonpersistent")
                self.assertEqual(result["diagnostic"]["failed"], 0)
                self.assertEqual(result["diagnostic"]["skipped_nonpersistent"], 1)
                self.assertIn("nonpersistent", result["diagnostic"]["message"])
                self.assertEqual(result["diagnostic"]["error_classes"], {})
            finally:
                store.close()

    def test_cross_project_acquire_executes_seed_slices_and_restores_source_project(self):
        fixture = {
            "name": "nishio",
            "displayName": "nishio",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Source",
                    "id": "cccccccccccccccccccccccc",
                    "created": 1,
                    "updated": 1,
                    "views": 100,
                    "lines": [
                        {"text": "Source", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "refs [/remote/PageA] and [/remote/PageB]", "created": 1, "updated": 1, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            store = SQLiteStore(store_path, project="nishio")
            client = CrossProjectAcquireClient()
            try:
                result = run_cross_project_acquire(
                    store,
                    client=client,
                    limit=1,
                    sample_limit=1,
                    seed_limit=2,
                    acquire_limit=2,
                    page_sample_limit=2,
                    failed_sample_limit=2,
                    top_links_limit=5,
                    summary_sample_limit=2,
                    project_url_base="https://scrapbox.io/",
                    local_suffix="semantic",
                    dry_run=False,
                )

                self.assertEqual(result["source_project"], "nishio")
                self.assertFalse(result["dry_run"])
                self.assertEqual(result["summary"]["planned_projects"], 1)
                self.assertEqual(result["summary"]["attempted_projects"], 1)
                self.assertEqual(result["summary"]["succeeded_projects"], 1)
                self.assertEqual(result["summary"]["fetched_pages"], 2)
                self.assertEqual(client.read_urls, ["https://scrapbox.io/remote/PageA", "https://scrapbox.io/remote/PageB"])
                project = result["projects"][0]
                self.assertEqual(project["status"], "acquired")
                self.assertEqual(project["local_project"], "remote:semantic")
                self.assertEqual([page["title"] for page in project["page_sample"]], ["PageA", "PageB"])
                self.assertEqual(project["reciprocal_refs"]["mention_count"], 2)
                self.assertEqual(
                    {target["title"] for target in project["reciprocal_refs"]["top_targets"]},
                    {"Origin", "Another"},
                )
                self.assertEqual(project["top_internal_links"][0]["title"], "Shared")
                self.assertEqual(project["top_internal_links"][0]["link_count"], 2)
                self.assertEqual(store.project, "nishio")

                store.project = "remote:semantic"
                self.assertEqual(store.resolve_page("PageA").title, "PageA")
                self.assertEqual(store.resolve_page("PageB").title, "PageB")
            finally:
                store.close()

    def test_cross_project_acquire_summarizes_all_failed_project(self):
        fixture = {
            "name": "nishio",
            "displayName": "nishio",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Source",
                    "id": "cccccccccccccccccccccccc",
                    "created": 1,
                    "updated": 1,
                    "views": 100,
                    "lines": [
                        {"text": "Source", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "refs [/remote/PageA] and [/remote/PageB]", "created": 1, "updated": 1, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)
            store = SQLiteStore(store_path, project="nishio")
            client = FailingAcquireClient()
            try:
                result = run_cross_project_acquire(
                    store,
                    client=client,
                    limit=1,
                    sample_limit=1,
                    seed_limit=2,
                    acquire_limit=2,
                    page_sample_limit=2,
                    failed_sample_limit=2,
                    top_links_limit=5,
                    summary_sample_limit=2,
                    project_url_base="https://scrapbox.io/",
                    local_suffix="semantic",
                    dry_run=False,
                )

                self.assertEqual(result["summary"]["attempted_projects"], 1)
                self.assertEqual(result["summary"]["empty_projects"], 1)
                self.assertEqual(result["summary"]["failed_pages"], 2)
                self.assertEqual(result["summary"]["diagnostic_counts"], {"all_failed": 1})
                project = result["projects"][0]
                self.assertEqual(project["status"], "empty")
                self.assertEqual(project["diagnostic_type"], "all_failed")
                self.assertEqual(project["diagnostic"]["error_classes"], {"command-env": 2})
                self.assertEqual(project["failed_page_sample"][0]["error_class"], "command-env")
            finally:
                store.close()


class _RateLimitThenOkRunner:
    """Fake subprocess.run: raise a transient CalledProcessError N times, then succeed."""

    def __init__(self, fail_times, stdout='{"ok": true}', stderr="cosense readPage ...: HTTP 429 Too Many Requests"):
        self.fail_times = fail_times
        self.stdout = stdout
        self.stderr = stderr
        self.calls = 0

    def __call__(self, command, check, text, capture_output):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise subprocess.CalledProcessError(1, command, output="", stderr=self.stderr)
        return subprocess.CompletedProcess(command, 0, stdout=self.stdout, stderr="")


class RateLimitRetryTest(unittest.TestCase):
    def test_classify_429_as_rate_limited(self):
        self.assertEqual(
            classify_cosense_cli_failure(returncode=1, stderr="HTTP 429 Too Many Requests", stdout=""),
            "rate-limited",
        )
        self.assertEqual(
            classify_cosense_cli_failure(returncode=1, stderr="rate limit exceeded", stdout=""),
            "rate-limited",
        )

    def test_run_json_retries_then_succeeds_with_exponential_backoff(self):
        delays: list[float] = []
        client = CosenseCliClient(
            max_retries=5, base_delay_seconds=2.0, max_delay_seconds=60.0, sleep=delays.append
        )
        runner = _RateLimitThenOkRunner(fail_times=3)
        with mock.patch("grasp.cosense_cli.subprocess.run", runner):
            result = client.read_page("https://scrapbox.io/p/A")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(runner.calls, 4)  # 3 rate-limited attempts + 1 success
        self.assertEqual(delays, [2.0, 4.0, 8.0])  # 2*2**0, 2*2**1, 2*2**2

    def test_backoff_is_capped_at_max_delay(self):
        delays: list[float] = []
        client = CosenseCliClient(
            max_retries=6, base_delay_seconds=10.0, max_delay_seconds=15.0, sleep=delays.append
        )
        runner = _RateLimitThenOkRunner(fail_times=4)
        with mock.patch("grasp.cosense_cli.subprocess.run", runner):
            client.read_page("https://scrapbox.io/p/A")
        self.assertEqual(delays, [10.0, 15.0, 15.0, 15.0])  # 10, 20→15, 40→15, 80→15

    def test_run_json_gives_up_after_max_retries(self):
        delays: list[float] = []
        client = CosenseCliClient(
            max_retries=2, base_delay_seconds=1.0, max_delay_seconds=60.0, sleep=delays.append
        )
        runner = _RateLimitThenOkRunner(fail_times=99)
        with mock.patch("grasp.cosense_cli.subprocess.run", runner):
            with self.assertRaises(CosenseCliError) as ctx:
                client.read_page("https://scrapbox.io/p/A")
        self.assertEqual(ctx.exception.error_class, "rate-limited")
        self.assertEqual(runner.calls, 3)  # initial attempt + 2 retries
        self.assertEqual(delays, [1.0, 2.0])

    def test_classify_transient_5xx_as_transient_server_error(self):
        for stderr in (
            "cosense readPage ...: HTTP 503 Service Unavailable",
            "HTTP 502 Bad Gateway",
            "HTTP 504 Gateway Timeout",
        ):
            with self.subTest(stderr=stderr):
                self.assertEqual(
                    classify_cosense_cli_failure(returncode=1, stderr=stderr, stdout=""),
                    "transient-server-error",
                )

    def test_page_body_digits_are_not_misread_as_5xx(self):
        # stdout can carry page text; a bare "503" there must not look like an outage.
        self.assertEqual(
            classify_cosense_cli_failure(returncode=1, stderr="", stdout="line about 503 buses"),
            "command-failed",
        )

    def test_transient_5xx_is_retried_like_429(self):
        delays: list[float] = []
        client = CosenseCliClient(
            max_retries=5, base_delay_seconds=2.0, max_delay_seconds=60.0, sleep=delays.append
        )
        runner = _RateLimitThenOkRunner(
            fail_times=2, stderr="cosense readPage ...: HTTP 503 Service Unavailable"
        )
        with mock.patch("grasp.cosense_cli.subprocess.run", runner):
            result = client.read_page("https://scrapbox.io/p/A")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(runner.calls, 3)
        self.assertEqual(delays, [2.0, 4.0])

    def test_transient_5xx_gives_up_with_its_own_error_class(self):
        client = CosenseCliClient(max_retries=1, base_delay_seconds=1.0, sleep=lambda _: None)
        runner = _RateLimitThenOkRunner(fail_times=99, stderr="HTTP 503 Service Unavailable")
        with mock.patch("grasp.cosense_cli.subprocess.run", runner):
            with self.assertRaises(CosenseCliError) as ctx:
                client.read_page("https://scrapbox.io/p/A")
        self.assertEqual(ctx.exception.error_class, "transient-server-error")

    def test_non_rate_limit_error_is_not_retried(self):
        delays: list[float] = []
        client = CosenseCliClient(sleep=delays.append)

        def runner(command, check, text, capture_output):
            raise subprocess.CalledProcessError(1, command, output="", stderr="403 Forbidden: not logged in")

        with mock.patch("grasp.cosense_cli.subprocess.run", runner):
            with self.assertRaises(CosenseCliError) as ctx:
                client.read_page("https://scrapbox.io/p/A")
        self.assertEqual(ctx.exception.error_class, "permission")
        self.assertEqual(delays, [])  # no backoff for non-429 failures

    def test_max_retries_zero_disables_retry(self):
        delays: list[float] = []
        client = CosenseCliClient(max_retries=0, sleep=delays.append)
        runner = _RateLimitThenOkRunner(fail_times=99)
        with mock.patch("grasp.cosense_cli.subprocess.run", runner):
            with self.assertRaises(CosenseCliError) as ctx:
                client.read_page("https://scrapbox.io/p/A")
        self.assertEqual(ctx.exception.error_class, "rate-limited")
        self.assertEqual(runner.calls, 1)
        self.assertEqual(delays, [])


if __name__ == "__main__":
    unittest.main()
