import json
import tempfile
import unittest
from pathlib import Path

from grasp.sqlite_store import SQLiteStore, import_cache_manifest_path, import_export_to_sqlite


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


OTHER_FIXTURE = {
    "name": "other",
    "displayName": "other",
    "exported": 2,
    "users": [],
    "pages": [
        {
            "title": "A",
            "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "created": 2,
            "updated": 40,
            "views": 5,
            "lines": [
                {"text": "A", "created": 2, "updated": 2, "userId": "u"},
                {"text": "other project links to [OtherMissing]", "created": 2, "updated": 3, "userId": "u"},
            ],
        }
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
            self.assertEqual(stats["unresolved_targets"], 1)
            manifest = json.loads(import_cache_manifest_path(store_path).read_text(encoding="utf-8"))
            cached_path = Path(manifest["projects"]["fixture"]["path"])
            self.assertEqual(manifest["last_imported_project"], "fixture")
            self.assertTrue(cached_path.exists())

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
                self.assertEqual(hits[0]["match_mode"], "literal")

                unresolved_targets = store.unresolved_targets()
                self.assertEqual(unresolved_targets[0]["title"], "Missing")
                self.assertEqual(unresolved_targets[0]["link_count"], 2)

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

                path = store.paths_between("A", "C", max_depth=2, limit=3)
                self.assertEqual(path["path_count"], 2)
                self.assertEqual(path["paths"][0]["distance"], 2)
                self.assertEqual(path["paths"][0]["nodes"][0]["title"], "A")
                self.assertEqual(path["paths"][0]["nodes"][-1]["title"], "C")
                self.assertIn(
                    ["page", "unresolved", "page"],
                    [[node["kind"] for node in path_item["nodes"]] for path_item in path["paths"]],
                )

                missing_hinge_path = store.paths_between("A", "Missing", max_depth=1, limit=1)
                self.assertEqual(missing_hinge_path["path_count"], 1)
                self.assertEqual(missing_hinge_path["paths"][0]["distance"], 1)
                self.assertEqual(missing_hinge_path["paths"][0]["nodes"][-1]["kind"], "unresolved")
                self.assertEqual(missing_hinge_path["paths"][0]["nodes"][-1]["title"], "Missing")

                no_path = store.paths_between("A", "Nope", max_depth=2, limit=1)
                self.assertEqual(no_path["path_count"], 0)
                self.assertIsNone(no_path["target"])
                self.assertIsNotNone(no_path["recovery_hints"]["target"])

                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["page"]["title"], "A")
                self.assertEqual(read["backlink_count_total"], 1)
                self.assertEqual(read["unresolved_targets"][0]["examples"][0]["source_title"], "A")
                self.assertNotIn("snippet_lines", read["related"][0])

                read_with_snippets = store.read(
                    "A",
                    backlink_limit=10,
                    related_limit=10,
                    unresolved_limit=10,
                    related_snippets=True,
                    related_snippet_lines=1,
                )
                self.assertEqual(read_with_snippets["related"][0]["title"], "C")
                self.assertEqual(
                    [line["text"] for line in read_with_snippets["related"][0]["snippet_lines"]],
                    ["C"],
                )
                self.assertTrue(read_with_snippets["related"][0]["snippet_truncated"])

                missing_read = store.read("Missing", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertIsNone(missing_read["page"])
                self.assertEqual(missing_read["backlink_count_total"], 2)
                self.assertEqual([item["title"] for item in missing_read["related"]], ["A", "C"])

                missing_read_with_snippets = store.read(
                    "Missing",
                    backlink_limit=10,
                    related_limit=10,
                    unresolved_limit=10,
                    related_snippets=True,
                    related_snippet_lines=1,
                )
                self.assertIsNone(missing_read_with_snippets["page"])
                self.assertEqual(
                    [line["text"] for line in missing_read_with_snippets["related"][0]["snippet_lines"]],
                    ["A"],
                )
                self.assertTrue(missing_read_with_snippets["related"][0]["snippet_truncated"])

                export_1hop = store.export_ai("A", depth=1, direct_limit=10)
                self.assertTrue(export_1hop["page_exists"])
                self.assertEqual(export_1hop["page_count"], 2)
                self.assertIn('type="mainpage"', export_1hop["text"])
                self.assertIn('<Page title="A"', export_1hop["text"])
                self.assertIn('<Page title="B"', export_1hop["text"])
                self.assertNotIn('<Page title="C"', export_1hop["text"])

                export_2hop = store.export_ai("A", depth=2, direct_limit=10, indirect_limit=10)
                self.assertEqual(export_2hop["page_count"], 3)
                self.assertEqual([page["title"] for page in export_2hop["pages"]], ["A", "B", "C"])
                self.assertIn('type="2hopLink"', export_2hop["text"])

                missing_export = store.export_ai("Missing", depth=1, direct_limit=10)
                self.assertFalse(missing_export["page_exists"])
                self.assertEqual([page["title"] for page in missing_export["pages"]], ["A", "C"])
                self.assertIn("main page not present in local store", missing_export["text"])
                self.assertNotIn('<Page title="Missing"', missing_export["text"])
            finally:
                store.close()

    def test_imports_multiple_projects_into_one_store_without_mixing_graphs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            other_export_path = Path(tmpdir) / "other.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            other_export_path.write_text(json.dumps(OTHER_FIXTURE), encoding="utf-8")

            fixture_stats = import_export_to_sqlite(export_path, store_path)
            other_stats = import_export_to_sqlite(other_export_path, store_path)

            self.assertEqual(fixture_stats["project"], "fixture")
            self.assertEqual(other_stats["project"], "other")
            self.assertEqual(other_stats["project_count"], 2)

            aggregate_store = SQLiteStore(store_path)
            fixture_store = SQLiteStore(store_path, project="fixture")
            other_store = SQLiteStore(store_path, project="other")
            try:
                aggregate_stats = aggregate_store.stats()
                self.assertIsNone(aggregate_stats["project"])
                self.assertEqual(aggregate_stats["project_count"], 2)
                self.assertEqual(aggregate_stats["pages"], 4)

                with self.assertRaises(ValueError):
                    aggregate_store.resolve_page("A")

                fixture_page = fixture_store.resolve_page("A")
                other_page = other_store.resolve_page("A")
                self.assertEqual(fixture_page.views, 100)
                self.assertEqual(other_page.views, 5)
                self.assertEqual(fixture_store.unresolved_targets()[0]["title"], "Missing")
                self.assertEqual(other_store.unresolved_targets()[0]["title"], "OtherMissing")
            finally:
                aggregate_store.close()
                fixture_store.close()
                other_store.close()

    def test_import_materializes_hash_tags_and_numeric_links(self):
        fixture = {
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
                        {
                            "text": "links to [2024] and #topic but not xs[0] or https://example.com/#fragment",
                            "created": 1,
                            "updated": 2,
                            "userId": "u",
                        },
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            stats = import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                self.assertEqual(stats["edges"], 2)
                self.assertEqual(stats["unresolved_targets"], 2)
                self.assertEqual(store.link_stats("2024")["link_count"], 1)
                self.assertEqual(store.link_stats("topic")["link_count"], 1)
                self.assertEqual(store.link_stats("0")["link_count"], 0)
                self.assertEqual(store.link_stats("fragment")["link_count"], 0)
            finally:
                store.close()

    def test_search_boolean_mode_supports_line_and_page_scope(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Both",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 30,
                    "views": 100,
                    "lines": [
                        {"text": "Both", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "alpha appears here", "created": 1, "updated": 2, "userId": "u"},
                        {"text": "beta appears later", "created": 1, "updated": 3, "userId": "u"},
                    ],
                },
                {
                    "title": "AOnly",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 20,
                    "views": 90,
                    "lines": [
                        {"text": "AOnly", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "alpha appears here too", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "BOnly",
                    "id": "cccccccccccccccccccccccc",
                    "created": 1,
                    "updated": 10,
                    "views": 80,
                    "lines": [
                        {"text": "BOnly", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "beta appears here too", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                literal_hits = store.search("alpha beta", limit=10)
                self.assertEqual(literal_hits, [])

                page_and_hits = store.search("alpha AND beta", mode="boolean", scope="page", limit=10)
                self.assertEqual([hit["source_title"] for hit in page_and_hits], ["Both", "Both"])
                self.assertEqual([hit["line_index"] for hit in page_and_hits], [1, 2])
                self.assertEqual(page_and_hits[0]["match_terms"], ["alpha"])
                self.assertEqual(page_and_hits[1]["match_terms"], ["beta"])
                self.assertEqual(page_and_hits[0]["match_mode"], "literal")

                implicit_page_and_hits = store.search("alpha beta", mode="boolean", scope="page", limit=10)
                self.assertEqual([hit["source_title"] for hit in implicit_page_and_hits], ["Both", "Both"])

                line_hits = store.search("alpha AND appears", mode="boolean", scope="line", limit=10)
                self.assertEqual([hit["source_title"] for hit in line_hits], ["Both", "AOnly"])

                page_not_hits = store.search("alpha AND NOT beta", mode="boolean", scope="page", limit=10)
                self.assertEqual([hit["source_title"] for hit in page_not_hits], ["AOnly"])

                line_or_hits = store.search("alpha OR beta", mode="boolean", scope="line", limit=10)
                self.assertEqual(
                    [hit["source_title"] for hit in line_or_hits],
                    ["Both", "Both", "AOnly", "BOnly"],
                )
            finally:
                store.close()

    def test_search_loose_normalization_matches_long_vowel_and_kana_width(self):
        fixture = {
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
                        {"text": "links to [ユーザーテスト]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                hits = store.search("ﾕｰｻﾞﾃｽﾄ", limit=3)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["source_title"], "A")
                self.assertEqual(hits[0]["line_index"], 1)
                self.assertEqual(hits[0]["match_mode"], "normalized")
                self.assertEqual(hits[0]["match_terms"], ["ユザテスト"])

                result = store.read("ユーザテスト", backlink_limit=3, related_limit=3, unresolved_limit=3)
                self.assertIsNone(result["page"])
                self.assertEqual(result["backlink_count_total"], 0)
                hints = result["recovery_hints"]
                self.assertIsNotNone(hints)
                self.assertEqual(hints["unresolved_targets"]["targets"][0]["title"], "ユーザーテスト")
                self.assertEqual(hints["search"]["hits"][0]["match_mode"], "normalized")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
