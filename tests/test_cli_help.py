import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


COMMANDS = [
    "import",
    "adopt-markdown",
    "import-forest",
    "stats",
    "read",
    "backlinks",
    "ambiguities",
    "cross-project-spread",
    "cross-project-spreads",
    "related",
    "path",
    "link-stats",
    "peek",
    "suggest",
    "search",
    "mentions",
    "co-links",
    "cross-project-refs",
    "cross-project-acquire",
    "gather",
    "export-ai",
    "export-markdown",
    "import-log-records",
    "log-records",
    "history",
    "append-section",
    "append-log",
    "write-page",
    "rename-page",
    "write-status",
    "write-diff",
    "revert-event",
    "replay-journal",
    "sync",
    "acquire",
    "unresolved",
]


def run_grasp_help(*args: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "grasp", *args, "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


class CliHelpTests(unittest.TestCase):
    def test_root_help_declares_mechanics_ssot(self):
        help_text = run_grasp_help()
        self.assertIn("Mechanics SSoT", help_text)
        self.assertIn("--json is also", help_text)
        self.assertIn("--full-ids", help_text)
        self.assertNotIn("--store .grasp/grasp.sqlite", help_text)
        self.assertNotIn("--export", help_text)
        self.assertNotIn("--rebuild-store", help_text)
        for command in COMMANDS:
            self.assertIn(command, help_text)

    def test_every_command_help_documents_returns_and_examples(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                help_text = run_grasp_help(command)
                self.assertIn("Returns (--json):", help_text)
                self.assertIn("Examples:", help_text)

    def test_help_uses_current_unresolved_mechanics(self):
        import_help = run_grasp_help("import")
        read_help = run_grasp_help("read")
        search_help = run_grasp_help("search")
        mentions_help = run_grasp_help("mentions")
        unresolved_help = run_grasp_help("unresolved")
        self.assertIn("--cosense", import_help)
        self.assertIn("--markdown", import_help)
        self.assertNotIn("--force", import_help)
        self.assertIn("--unresolved-limit", read_help)
        self.assertIn("--around-line", read_help)
        self.assertIn("line_window", read_help)
        self.assertIn("--related-snippet-mode", read_help)
        self.assertIn("--line-offset", run_grasp_help("peek"))
        self.assertIn("--context", search_help)
        self.assertIn("context_window", search_help)
        self.assertIn("--unlinked", mentions_help)
        self.assertIn("unresolved_targets", read_help)
        self.assertIn("link_count", unresolved_help)
        self.assertNotIn("--wanted-limit", read_help)

    def test_import_accepts_cosense_export_path_and_replaces_existing_store(self):
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
                    "updated": 1,
                    "views": 0,
                    "lines": [{"text": "A", "created": 1, "updated": 1, "userId": "u"}],
                }
            ],
        }
        replacement_fixture = {
            **fixture,
            "pages": [
                *fixture["pages"],
                {
                    "title": "B",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 1,
                    "views": 0,
                    "lines": [{"text": "B", "created": 1, "updated": 1, "userId": "u"}],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            export_path.write_text(json.dumps(replacement_fixture), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["lines"], 2)

    def test_old_schema_store_recovers_silently_from_cached_import(self):
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
                    "updated": 1,
                    "views": 0,
                    "lines": [{"text": "A", "created": 1, "updated": 1, "userId": "u"}],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            export_path.unlink()
            connection = sqlite3.connect(store_path)
            try:
                connection.execute(
                    "UPDATE metadata SET value = '3' WHERE key = 'schema_version'"
                )
                connection.commit()
            finally:
                connection.close()

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "peek",
                    "A",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(result["page"]["title"], "A")
        self.assertEqual([line["text"] for line in result["lines"]], ["A"])

    def test_old_schema_markdown_store_recovers_all_projects_from_import_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_a = Path(tmpdir) / "wiki-a"
            root_a.mkdir()
            (root_a / "A.md").write_text("# A\n", encoding="utf-8")
            (root_a / "raw").mkdir()
            (root_a / "raw" / "Raw.md").write_text("# Raw\n", encoding="utf-8")
            root_b = Path(tmpdir) / "wiki-b"
            root_b.mkdir()
            (root_b / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root_a),
                    "--project",
                    "wiki-a",
                    "--markdown-exclude-dir",
                    "raw",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root_b),
                    "--project",
                    "wiki-b",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                connection.execute("UPDATE metadata SET value = '5' WHERE key = 'schema_version'")
                connection.commit()
            finally:
                connection.close()

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki-b",
                    "read",
                    "B",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            stats_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki-a",
                    "stats",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        stats = json.loads(stats_completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(result["page"]["title"], "B")
        self.assertEqual(stats["project_count"], 2)
        self.assertEqual(stats["pages"], 1)

    def test_json_is_accepted_after_subcommand(self):
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
                    "updated": 1,
                    "views": 0,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "links to [B]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "B",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 2,
                    "views": 0,
                    "lines": [
                        {"text": "B", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "links to [A]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "C",
                    "id": "cccccccccccccccccccccccc",
                    "created": 1,
                    "updated": 3,
                    "views": 0,
                    "lines": [
                        {"text": "C", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "links to [B]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "read",
                    "A",
                    "--json",
                    "--line-limit",
                    "1",
                    "--related-snippets",
                    "--related-snippet-lines",
                    "1",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            edge_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "read",
                    "A",
                    "--json",
                    "--line-limit",
                    "1",
                    "--related-snippets",
                    "--related-snippet-lines",
                    "1",
                    "--related-snippet-mode",
                    "edge",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["page"]["title"], "A")
        self.assertEqual(result["lines"][0]["text"], "A")
        self.assertIsNone(result["line_window"])
        self.assertEqual(result["related"][0]["title"], "C")
        self.assertEqual(result["related"][0]["snippet_lines"][0]["text"], "C")
        self.assertEqual(result["related"][0]["snippet_mode"], "lead")
        self.assertTrue(result["related"][0]["snippet_truncated"])

        edge_result = json.loads(edge_completed.stdout)
        self.assertEqual(edge_result["related"][0]["snippet_lines"][0]["text"], "links to [B]")
        self.assertEqual(edge_result["related"][0]["snippet_mode"], "edge")
        self.assertEqual(edge_result["related"][0]["snippet_window"]["context_line_id"], "cccccccccccccccccccccccc:1")

    def test_read_around_line_json_returns_bounded_window(self):
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
                    "updated": 1,
                    "views": 0,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "before", "created": 1, "updated": 2, "userId": "u"},
                        {"text": "center", "created": 1, "updated": 3, "userId": "u"},
                        {"text": "after", "created": 1, "updated": 4, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "read",
                    "--around-line",
                    "aaaaaaaaaaaaaaaaaaaaaaaa:2",
                    "--line-context",
                    "1",
                    "--backlinks-limit",
                    "0",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["page"]["title"], "A")
        self.assertEqual([line["text"] for line in result["lines"]], ["before", "center", "after"])
        self.assertEqual(result["line_window"]["around_line_id"], "aaaaaaaaaaaaaaaaaaaaaaaa:2")
        self.assertEqual(result["line_window"]["start_index"], 1)
        self.assertEqual(result["line_window"]["end_index"], 3)
        self.assertTrue(result["line_window"]["truncated_before"])
        self.assertFalse(result["line_window"]["truncated_after"])
        self.assertTrue(result["lines_truncated"])

    def test_text_output_uses_local_line_id_aliases_by_default(self):
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
                    "updated": 1,
                    "views": 0,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "body", "created": 1, "updated": 2, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            compact = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "peek",
                    "A",
                    "--line-limit",
                    "2",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            full = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "peek",
                    "A",
                    "--line-limit",
                    "1",
                    "--full-ids",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        self.assertIn("line-id aliases: P1=aaaaaaaaaaaaaaaaaaaaaaaa", compact.stdout)
        self.assertIn("P1:0  A", compact.stdout)
        self.assertIn("P1:1  body", compact.stdout)
        self.assertNotIn("aaaaaaaaaaaaaaaaaaaaaaaa:0", compact.stdout)
        self.assertNotIn("line-id aliases:", full.stdout)
        self.assertIn("aaaaaaaaaaaaaaaaaaaaaaaa:0  A", full.stdout)

    def test_peek_supports_line_offset_in_json_and_text_output(self):
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
                    "updated": 1,
                    "views": 0,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "one", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "two", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "three", "created": 1, "updated": 1, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            json_output = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "peek",
                    "A",
                    "--line-offset",
                    "1",
                    "--line-limit",
                    "2",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            text_output = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "peek",
                    "A",
                    "--line-offset",
                    "1",
                    "--line-limit",
                    "2",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(json_output.stdout)
        self.assertEqual(result["line_offset"], 1)
        self.assertEqual([line["text"] for line in result["lines"]], ["one", "two"])
        self.assertTrue(result["lines_truncated"])
        self.assertTrue(result["lines_truncated_before"])
        self.assertTrue(result["lines_truncated_after"])
        self.assertIn("line_offset: 1", text_output.stdout)
        self.assertIn("...\nP1:1  one\nP1:2  two\n...\n", text_output.stdout)
        self.assertNotIn("P1:0  A", text_output.stdout)

    def test_search_json_includes_normalized_match_mode_for_loose_hits(self):
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
                    "updated": 1,
                    "views": 0,
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
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "search",
                    "ユーザテスト",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(len(result["hits"]), 1)
        self.assertEqual(result["hits"][0]["source_title"], "A")
        self.assertEqual(result["hits"][0]["match_mode"], "normalized")
        self.assertEqual(result["mode"], "literal")
        self.assertEqual(result["scope"], "line")
        self.assertIsNone(result["recovery_hints"])

    def test_search_boolean_json_supports_page_scope(self):
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
                    "updated": 2,
                    "views": 10,
                    "lines": [
                        {"text": "Both", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "alpha appears here", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "beta appears there", "created": 1, "updated": 1, "userId": "u"},
                    ],
                },
                {
                    "title": "AlphaOnly",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 1,
                    "views": 9,
                    "lines": [
                        {"text": "AlphaOnly", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "alpha appears here", "created": 1, "updated": 1, "userId": "u"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "search",
                    "alpha AND beta",
                    "--mode",
                    "boolean",
                    "--scope",
                    "page",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["mode"], "boolean")
        self.assertEqual(result["scope"], "page")
        self.assertEqual([hit["source_title"] for hit in result["hits"]], ["Both", "Both"])
        self.assertEqual([hit["match_terms"] for hit in result["hits"]], [["alpha"], ["beta"]])
        self.assertIsNone(result["recovery_hints"])

    def test_search_json_includes_context_lines_when_requested(self):
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
                    "updated": 1,
                    "views": 0,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "before", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "needle appears", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "after", "created": 1, "updated": 1, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "search",
                    "needle",
                    "--context",
                    "1",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["context"], 1)
        self.assertEqual(
            [line["text"] for line in result["hits"][0]["context_lines"]],
            ["before", "needle appears", "after"],
        )
        self.assertEqual(result["hits"][0]["context_window"]["start_index"], 1)
        self.assertEqual(result["hits"][0]["context_window"]["end_index"], 3)

    def test_related_empty_json_includes_recovery_hints(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Alpha",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 1,
                    "views": 10,
                    "lines": [{"text": "Alpha", "created": 1, "updated": 1, "userId": "u"}],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "related",
                    "Al",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["related"], [])
        self.assertEqual(result["recovery_hints"]["suggest"]["suggestions"][0]["title"], "Alpha")

    def test_path_json_returns_unresolved_hinge(self):
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
                    "updated": 1,
                    "views": 10,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "links to [Shared]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "B",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 1,
                    "views": 9,
                    "lines": [
                        {"text": "B", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "also links to [Shared]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "path",
                    "A",
                    "B",
                    "--max-depth",
                    "2",
                    "--limit",
                    "1",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            no_path_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "path",
                    "A",
                    "B",
                    "--max-depth",
                    "1",
                    "--limit",
                    "1",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["path_count"], 1)
        self.assertEqual(result["paths"][0]["distance"], 2)
        self.assertEqual([node["title"] for node in result["paths"][0]["nodes"]], ["A", "Shared", "B"])
        self.assertEqual(result["paths"][0]["nodes"][1]["kind"], "unresolved")
        self.assertEqual(result["paths"][0]["edges"][0]["line_text"], "links to [Shared]")

        no_path_result = json.loads(no_path_completed.stdout)
        self.assertEqual(no_path_result["path_count"], 0)
        self.assertEqual(no_path_result["recovery_hints"]["path"]["reason"], "no_path_within_max_depth")
        self.assertEqual(no_path_result["recovery_hints"]["path"]["next_max_depth"], 2)
        self.assertEqual(no_path_result["recovery_hints"]["path"]["source_link_stats"]["title"], "A")
        self.assertEqual(no_path_result["recovery_hints"]["path"]["target_link_stats"]["title"], "B")

    def test_missing_store_stats_returns_friendly_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "missing.sqlite"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "stats",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertFalse(result["schema_ok"])
        self.assertEqual(result["diagnostic"]["type"], "store_missing")
        self.assertIn("grasp import --cosense <json>", result["diagnostic"]["next_actions"][0])

    def test_import_cosense_with_folder_points_to_markdown_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "import",
                    "--cosense",
                    tmpdir,
                ],
                text=True,
                capture_output=True,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("grasp import --markdown <folder>", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_import_markdown_folder_indexes_read_only_mirror(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nlinks to [[B]] and [[Missing]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nlinks to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            read_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "A",
                    "--backlinks-limit",
                    "10",
                    "--unresolved-limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        import_result = json.loads(import_completed.stdout)
        read_result = json.loads(read_completed.stdout)
        self.assertEqual(import_result["pages"], 2)
        self.assertEqual(import_result["edges"], 3)
        self.assertEqual(read_result["page"]["title"], "A")
        self.assertEqual(read_result["backlink_count_total"], 1)
        self.assertEqual(read_result["unresolved_targets"][0]["title"], "Missing")

    def test_adopt_markdown_writes_journal_and_export_check_noops(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            adopt_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            check_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            (root / "A.md").write_text("# A\nlinks to [[B]]\nchanged\n", encoding="utf-8")
            dirty_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--check",
                ],
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]

        adopt_result = json.loads(adopt_completed.stdout)
        check_result = json.loads(check_completed.stdout)
        dirty_result = json.loads(dirty_completed.stdout)

        self.assertEqual(adopt_result["journal_events"], 2)
        self.assertEqual(adopt_result["adopted_pages"], 2)
        self.assertEqual([event["event_type"] for event in journal_events], ["page_create", "page_create"])
        self.assertEqual(journal_events[0]["project"], "wiki")
        self.assertIn("lines", journal_events[0]["payload"])
        self.assertTrue(check_result["ok"])
        self.assertEqual(check_result["changed_files"], [])
        self.assertEqual(dirty_completed.returncode, 1)
        self.assertFalse(dirty_result["ok"])
        self.assertEqual(dirty_result["changed_files"], ["A.md"])

    def test_adopt_markdown_imports_log_entry_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "Log.md").write_text(
                "# Log\n\n"
                "## [2026-06-26 01:00] implementation | first entry\n"
                "- touched [[A]]\n\n"
                "## [2026-06-26 02:00] lint | second entry\n"
                "- clean\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            adopt_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            status_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-status",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                    "--strict",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]

        adopt_result = json.loads(adopt_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        status_result = json.loads(status_completed.stdout)
        log_events = [event for event in journal_events if event["event_type"] == "log_entry_import"]
        self.assertEqual(adopt_result["adopted_pages"], 2)
        self.assertEqual(adopt_result["log_entry_records"], 2)
        self.assertEqual(adopt_result["journal_events"], 4)
        self.assertEqual(
            [event["event_type"] for event in journal_events],
            ["page_create", "page_create", "log_entry_import", "log_entry_import"],
        )
        self.assertEqual(log_events[0]["payload"]["timestamp"], "2026-06-26 01:00")
        self.assertEqual(log_events[0]["payload"]["op"], "implementation")
        self.assertEqual(log_events[0]["payload"]["summary"], "first entry")
        self.assertEqual(log_events[0]["payload"]["source_path"], "Log.md")
        self.assertEqual(log_events[0]["payload"]["body_line_count"], 1)
        self.assertEqual(len(log_events[0]["payload"]["record_id"]), 24)
        self.assertTrue(log_events[0]["event_id"].startswith("log-entry-"))
        self.assertTrue(replay_result["ok"])
        self.assertEqual(status_result["journal_log_record_count"], 2)

    def test_import_log_records_appends_only_missing_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            log_path = root / "Log.md"
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            log_path.write_text(
                "# Log\n\n"
                "## [2026-06-26 01:00] implementation | first entry\n"
                "- touched [[A]]\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            log_path.write_text(
                log_path.read_text(encoding="utf-8")
                + "\n## [2026-06-26 02:00] implementation | second entry\n"
                + "- new record\n",
                encoding="utf-8",
            )
            import_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "import-log-records",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            second_import_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "import-log-records",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]

        import_result = json.loads(import_completed.stdout)
        second_import_result = json.loads(second_import_completed.stdout)
        log_events = [event for event in journal_events if event["event_type"] == "log_entry_import"]
        self.assertEqual(import_result["scanned_records"], 2)
        self.assertEqual(import_result["imported_records"], 1)
        self.assertEqual(import_result["skipped_records"], 1)
        self.assertEqual(second_import_result["imported_records"], 0)
        self.assertEqual(second_import_result["skipped_records"], 2)
        self.assertEqual(len(log_events), 2)

    def test_import_log_records_does_not_duplicate_legacy_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "Alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (root / "Log.md").write_text(
                "# Log\n\n"
                "## [2026-06-26 01:00] implementation | first entry\n"
                "- touched [[Alpha]]\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            for event in journal_events:
                if event["event_type"] != "log_entry_import":
                    continue
                payload = event["payload"]
                for key in (
                    "content_fingerprint",
                    "record_identity",
                    "subjects",
                    "explicit_subjects",
                    "heuristic_subjects",
                    "subject_source",
                    "sources",
                ):
                    payload.pop(key, None)
            journal_path.write_text(
                "\n".join(
                    json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    for event in journal_events
                )
                + "\n",
                encoding="utf-8",
            )
            import_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "import-log-records",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            updated_journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]

        import_result = json.loads(import_completed.stdout)
        log_events = [event for event in updated_journal_events if event["event_type"] == "log_entry_import"]
        self.assertEqual(import_result["imported_records"], 0)
        self.assertEqual(import_result["skipped_records"], 1)
        self.assertEqual(len(log_events), 1)

    def test_record_per_file_log_entry_uses_explicit_subjects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            log_dir = root / "log"
            log_dir.mkdir(parents=True)
            (root / "Alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (root / "Beta.md").write_text("# Beta\n", encoding="utf-8")
            (root / "Gamma.md").write_text("# Gamma\n", encoding="utf-8")
            (log_dir / "entry.md").write_text(
                "---\n"
                "type: log-entry\n"
                "date: 2026-06-26 03:00\n"
                "op: decision\n"
                "summary: explicit entry\n"
                "subjects:\n"
                "  - Alpha\n"
                "pages: [Beta]\n"
                "sources:\n"
                "  - raw/session.txt\n"
                "---\n"
                "# explicit entry\n\n"
                "- body mentions [[Gamma]] and notes/Delta.md\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            history_alpha_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(Path(tmpdir) / "missing.sqlite"),
                    "--project",
                    "wiki",
                    "history",
                    "Alpha",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            history_gamma_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(Path(tmpdir) / "missing.sqlite"),
                    "--project",
                    "wiki",
                    "history",
                    "Gamma",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]

        log_events = [event for event in journal_events if event["event_type"] == "log_entry_import"]
        payload = log_events[0]["payload"]
        history_alpha = json.loads(history_alpha_completed.stdout)
        history_gamma = json.loads(history_gamma_completed.stdout)
        self.assertEqual(len(log_events), 1)
        self.assertEqual(payload["record_format"], "file")
        self.assertEqual(payload["timestamp"], "2026-06-26 03:00")
        self.assertEqual(payload["op"], "decision")
        self.assertEqual(payload["summary"], "explicit entry")
        self.assertEqual(payload["subjects"], ["Alpha", "Beta"])
        self.assertEqual(payload["explicit_subjects"], ["Alpha", "Beta"])
        self.assertEqual(payload["heuristic_subjects"], ["Gamma", "Delta"])
        self.assertEqual(payload["subject_source"], "frontmatter")
        self.assertEqual(payload["sources"], ["raw/session.txt"])
        self.assertEqual(payload["body_line_count"], 1)
        self.assertEqual(history_alpha["matched_records"], 1)
        self.assertEqual(history_alpha["records"][0]["subjects"], ["Alpha", "Beta"])
        self.assertEqual(history_gamma["matched_records"], 0)

    def test_record_per_file_log_entry_update_appends_new_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            log_dir = root / "log"
            log_dir.mkdir(parents=True)
            (root / "Alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (root / "Beta.md").write_text("# Beta\n", encoding="utf-8")
            entry_path = log_dir / "entry.md"
            entry_path.write_text(
                "---\n"
                "type: log-entry\n"
                "date: 2026-06-26 03:00\n"
                "op: decision\n"
                "summary: explicit entry\n"
                "subjects:\n"
                "  - Alpha\n"
                "sources:\n"
                "  - raw/a.txt\n"
                "---\n"
                "# explicit entry\n\n"
                "- first body\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            missing_store_path = Path(tmpdir) / "missing.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            entry_path.write_text(
                "---\n"
                "type: log-entry\n"
                "date: 2026-06-26 03:00\n"
                "op: decision\n"
                "summary: explicit entry\n"
                "subjects:\n"
                "  - Beta\n"
                "sources:\n"
                "  - raw/b.txt\n"
                "---\n"
                "# explicit entry\n\n"
                "- second body\n",
                encoding="utf-8",
            )
            import_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "import-log-records",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            second_import_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "import-log-records",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            history_alpha_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(missing_store_path),
                    "--project",
                    "wiki",
                    "history",
                    "Alpha",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            history_beta_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(missing_store_path),
                    "--project",
                    "wiki",
                    "history",
                    "Beta",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            all_versions_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(missing_store_path),
                    "--project",
                    "wiki",
                    "log-records",
                    "--journal",
                    str(journal_path),
                    "--include-superseded",
                    "--oldest-first",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]

        import_result = json.loads(import_completed.stdout)
        second_import_result = json.loads(second_import_completed.stdout)
        history_alpha = json.loads(history_alpha_completed.stdout)
        history_beta = json.loads(history_beta_completed.stdout)
        all_versions = json.loads(all_versions_completed.stdout)
        log_events = [event for event in journal_events if event["event_type"] == "log_entry_import"]
        first_payload = log_events[0]["payload"]
        second_payload = log_events[1]["payload"]
        self.assertEqual(import_result["imported_records"], 1)
        self.assertEqual(import_result["updated_records"], 1)
        self.assertEqual(import_result["new_records"], 0)
        self.assertEqual(second_import_result["imported_records"], 0)
        self.assertEqual(second_import_result["skipped_records"], 1)
        self.assertEqual(len(log_events), 2)
        self.assertEqual(first_payload["record_id"], second_payload["record_id"])
        self.assertNotEqual(first_payload["content_fingerprint"], second_payload["content_fingerprint"])
        self.assertEqual(history_alpha["matched_records"], 0)
        self.assertEqual(history_beta["matched_records"], 1)
        self.assertEqual(history_beta["total_records"], 1)
        self.assertEqual(history_beta["total_record_events"], 2)
        self.assertEqual(history_beta["superseded_record_events"], 1)
        self.assertEqual(history_beta["records"][0]["record_version"], 2)
        self.assertEqual(history_beta["records"][0]["record_version_count"], 2)
        self.assertIsNone(history_beta["records"][0]["superseded_by"])
        self.assertEqual(all_versions["returned_records"], 2)
        self.assertEqual(all_versions["records"][0]["record_version"], 1)
        self.assertEqual(all_versions["records"][0]["superseded_by"]["event_id"], log_events[1]["event_id"])
        self.assertEqual(all_versions["records"][1]["record_version"], 2)

    def test_log_records_and_history_query_journal_without_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "Alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (root / "Log.md").write_text(
                "# Log\n\n"
                "## [2026-06-26 01:00] implementation | first entry\n"
                "- PR #1 touched [[Alpha]]\n\n"
                "## [2026-06-26 02:00] fix | second entry\n"
                "- refined [[Alpha]]\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            missing_store_path = Path(tmpdir) / "missing.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            newest_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(missing_store_path),
                    "--project",
                    "wiki",
                    "log-records",
                    "--journal",
                    str(journal_path),
                    "--limit",
                    "1",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            filtered_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(missing_store_path),
                    "--project",
                    "wiki",
                    "log-records",
                    "--journal",
                    str(journal_path),
                    "--query",
                    "touched [[Alpha]]",
                    "--source-path",
                    "Log.md",
                    "--op",
                    "implementation",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            history_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(missing_store_path),
                    "--project",
                    "wiki",
                    "history",
                    "Alpha",
                    "--journal",
                    str(journal_path),
                    "--oldest-first",
                    "--limit",
                    "1",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            bad_limit_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(missing_store_path),
                    "--project",
                    "wiki",
                    "log-records",
                    "--journal",
                    str(journal_path),
                    "--limit",
                    "0",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

        newest_result = json.loads(newest_completed.stdout)
        filtered_result = json.loads(filtered_completed.stdout)
        history_result = json.loads(history_completed.stdout)
        self.assertEqual(newest_result["total_records"], 2)
        self.assertEqual(newest_result["returned_records"], 1)
        self.assertEqual(newest_result["records"][0]["summary"], "second entry")
        self.assertEqual(newest_result["records"][0]["subjects"], ["Alpha"])
        self.assertEqual(filtered_result["matched_records"], 1)
        self.assertEqual(filtered_result["records"][0]["summary"], "first entry")
        self.assertEqual(filtered_result["records"][0]["body_text"], "- PR #1 touched [[Alpha]]")
        self.assertEqual(filtered_result["records"][0]["subjects"], ["Alpha"])
        self.assertEqual(history_result["query"], "Alpha")
        self.assertEqual(history_result["matched_records"], 2)
        self.assertEqual(history_result["records"][0]["op"], "implementation")
        self.assertEqual(history_result["records"][0]["subjects"], ["Alpha"])
        self.assertEqual(history_result["records"][0]["later_event_count"], 1)
        self.assertEqual(history_result["records"][0]["later_events"][0]["summary"], "second entry")
        self.assertEqual(history_result["records"][0]["later_events"][0]["shared_subjects"], ["Alpha"])
        self.assertNotEqual(bad_limit_completed.returncode, 0)
        self.assertIn("--limit must be >= 1", bad_limit_completed.stderr)

    def test_export_markdown_can_regenerate_index_and_log_projection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            (root / "concepts").mkdir(parents=True)
            (root / "source").mkdir()
            (root / "index.md").write_text("# Hand index\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            (root / "concepts" / "A.md").write_text(
                "---\ntype: concept\nsummary: Alpha summary\n---\n# A\n",
                encoding="utf-8",
            )
            (root / "source" / "Digest.md").write_text(
                "---\ntype: source\nsummary: Source summary\n---\n# Digest\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "append-log",
                    "--timestamp",
                    "2026-06-26 15:00",
                    "--op",
                    "test",
                    "--summary",
                    "generated log",
                    "--line",
                    "- ok",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            dirty_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--regenerate-index",
                    "--regenerate-log",
                    "--journal",
                    str(journal_path),
                    "--check",
                ],
                text=True,
                capture_output=True,
            )
            write_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--regenerate-index",
                    "--regenerate-log",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            clean_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--regenerate-index",
                    "--regenerate-log",
                    "--journal",
                    str(journal_path),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            index_text = (root / "index.md").read_text(encoding="utf-8")
            log_text = (root / "Log.md").read_text(encoding="utf-8")

        dirty_result = json.loads(dirty_completed.stdout)
        write_result = json.loads(write_completed.stdout)
        clean_result = json.loads(clean_completed.stdout)
        self.assertEqual(dirty_completed.returncode, 1)
        self.assertEqual(dirty_result["regenerated_files"], ["Log.md", "index.md"])
        self.assertEqual(dirty_result["changed_files"], ["index.md"])
        self.assertEqual(write_result["written_files"], ["index.md"])
        self.assertEqual(write_result["regenerated_files"], ["Log.md", "index.md"])
        self.assertTrue(clean_result["ok"])
        self.assertIn("| [A](concepts/A.md) | Alpha summary |", index_text)
        self.assertIn("| [Digest](source/Digest.md) | Source summary |", index_text)
        self.assertEqual(log_text, "# Log\n\n## [2026-06-26 15:00] test | generated log\n- ok\n")

    def test_export_markdown_regenerates_log_from_latest_record_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            log_dir = root / "log"
            log_dir.mkdir(parents=True)
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            (root / "Alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (root / "Beta.md").write_text("# Beta\n", encoding="utf-8")
            (log_dir / "entry.md").write_text(
                "---\n"
                "type: log-entry\n"
                "date: 2026-06-26 03:00\n"
                "op: decision\n"
                "summary: projected record\n"
                "subjects:\n"
                "  - Alpha\n"
                "---\n"
                "# projected record\n\n"
                "- first body [[Alpha]]\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            record_event = next(event for event in journal_events if event["event_type"] == "log_entry_import")
            updated_event = json.loads(json.dumps(record_event))
            updated_event["event_id"] = "log-entry-updated"
            updated_event["created_at"] = "2026-06-26T04:00:00+00:00"
            updated_event["payload"]["summary"] = "projected record updated"
            updated_event["payload"]["subjects"] = ["Beta"]
            updated_event["payload"]["explicit_subjects"] = ["Beta"]
            updated_event["payload"]["content_fingerprint"] = "updated-fingerprint"
            updated_event["payload"]["body_lines"][0]["text"] = "- second body [[Beta]]"
            journal_events.append(updated_event)
            journal_path.write_text(
                "\n".join(
                    json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    for event in journal_events
                )
                + "\n",
                encoding="utf-8",
            )

            dirty_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--regenerate-log",
                    "--journal",
                    str(journal_path),
                    "--check",
                ],
                text=True,
                capture_output=True,
            )
            write_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--regenerate-log",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            status_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-status",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                    "--strict",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            log_text = (root / "Log.md").read_text(encoding="utf-8")

        dirty_result = json.loads(dirty_completed.stdout)
        write_result = json.loads(write_completed.stdout)
        status_result = json.loads(status_completed.stdout)
        self.assertEqual(dirty_completed.returncode, 1)
        self.assertEqual(dirty_result["changed_files"], ["Log.md"])
        self.assertEqual(write_result["written_files"], ["Log.md"])
        self.assertEqual(write_result["regenerated_files"], ["Log.md"])
        self.assertTrue(status_result["strict_ok"])
        self.assertEqual(
            log_text,
            "# Log\n\n"
            "## [2026-06-26 03:00] decision | projected record updated\n"
            "- second body [[Beta]]\n",
        )
        self.assertNotIn("first body", log_text)

    def test_write_page_create_writes_page_create_journal_and_projection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nlink [[New]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            create_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-page",
                    "New",
                    "--create",
                    "--path",
                    "New.md",
                    "--line",
                    "# New",
                    "--line",
                    "body [[A]]",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            read_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "New",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            new_text = (root / "New.md").read_text(encoding="utf-8")
            revert_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "revert-event",
                    json.loads(create_completed.stdout)["event_id"],
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            replay_after_revert_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            new_exists_after_revert = (root / "New.md").exists()

        create_result = json.loads(create_completed.stdout)
        read_result = json.loads(read_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        revert_result = json.loads(revert_completed.stdout)
        replay_after_revert = json.loads(replay_after_revert_completed.stdout)
        self.assertEqual([event["event_type"] for event in journal_events], ["page_create", "page_create", "event_revert"])
        self.assertEqual(create_result["event_type"], "page_create")
        self.assertEqual(create_result["source_path"], "New.md")
        self.assertEqual(create_result["previous_line_count"], 0)
        self.assertEqual(create_result["line_count"], 2)
        self.assertEqual(create_result["edge_count"], 1)
        self.assertEqual(create_result["projection"]["written_files"], ["New.md"])
        self.assertEqual(new_text, "# New\nbody [[A]]\n")
        self.assertEqual(read_result["page"]["title"], "New")
        self.assertEqual(read_result["backlink_count_total"], 1)
        self.assertTrue(replay_result["ok"])
        self.assertEqual(revert_result["target_event_type"], "page_create")
        self.assertEqual(revert_result["removed_line_count"], 2)
        self.assertEqual(revert_result["projection"]["removed_files"], ["New.md"])
        self.assertFalse(new_exists_after_revert)
        self.assertTrue(replay_after_revert["ok"])

    def test_replay_journal_page_update_tolerates_line_id_drift_when_text_matches(self):
        def event(event_type, event_id, payload):
            return {
                "schema_version": 1,
                "event_id": event_id,
                "event_type": event_type,
                "project": "wiki",
                "created_at": "2026-06-26T00:00:00+00:00",
                "payload": payload,
            }

        def line(line_id, line_index, text):
            return {
                "line_id": line_id,
                "line_index": line_index,
                "text": text,
                "created": None,
                "updated": None,
                "user_id": None,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nnew\n", encoding="utf-8")
            journal_path = Path(tmpdir) / "events.jsonl"
            events = [
                event(
                    "page_create",
                    "create-a",
                    {
                        "page_id": "6114958182d722e68f0f5687",
                        "title": "A",
                        "source_path": "A.md",
                        "aliases": ["A"],
                        "lines": [line("created-0", 0, "# A"), line("created-1", 1, "old")],
                    },
                ),
                event(
                    "page_update",
                    "update-a",
                    {
                        "page_id": "6114958182d722e68f0f5687",
                        "title": "A",
                        "previous_lines": [line("reimported-0", 0, "# A"), line("reimported-1", 1, "old")],
                        "lines": [line("updated-0", 0, "# A"), line("updated-1", 1, "new")],
                    },
                ),
            ]
            journal_path.write_text(
                "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in events),
                encoding="utf-8",
            )

            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        replay_result = json.loads(replay_completed.stdout)
        self.assertTrue(replay_result["ok"])

    def test_projection_export_failure_appends_revert_and_restores_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            (root / "A.md").unlink()
            (root / "A.md").mkdir()
            failed_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "append-section",
                    "A",
                    "--heading",
                    "Broken export",
                    "--line",
                    "- should rollback",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                text=True,
                capture_output=True,
            )
            peek_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "peek",
                    "A",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            replay_root = Path(tmpdir) / "replay"
            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(replay_root),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            replay_text = (replay_root / "A.md").read_text(encoding="utf-8")

        peek_result = json.loads(peek_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("store was reverted with event", failed_completed.stderr)
        self.assertEqual([event["event_type"] for event in journal_events], ["page_create", "section_append", "event_revert"])
        self.assertEqual(journal_events[-1]["payload"]["target_event_id"], journal_events[1]["event_id"])
        self.assertEqual(journal_events[-1]["payload"]["target_event_type"], "section_append")
        self.assertIn("projection export failed", journal_events[-1]["payload"]["reason"])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(replay_text, "# A\n")
        self.assertEqual(replay_result["written_files"], ["A.md"])

    def test_append_section_and_log_update_store_journal_and_projection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            section_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "append-section",
                    "A",
                    "--heading",
                    "Updates",
                    "--line",
                    "- detail [[B]]",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            log_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "append-log",
                    "--timestamp",
                    "2026-06-26 01:00",
                    "--op",
                    "test",
                    "--summary",
                    "append smoke",
                    "--line",
                    "- ok",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            log_result = json.loads(log_completed.stdout)
            status_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-status",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                    "--strict",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            diff_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-diff",
                    "--output",
                    str(root),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            revert_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "revert-event",
                    log_result["event_id"],
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            write_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-page",
                    "A",
                    "--line",
                    "# A",
                    "--line",
                    "- rewritten [[C]]",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            write_result = json.loads(write_completed.stdout)
            revert_write_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "revert-event",
                    write_result["event_id"],
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            page_text = (root / "A.md").read_text(encoding="utf-8")
            log_text = (root / "Log.md").read_text(encoding="utf-8")

        section_result = json.loads(section_completed.stdout)
        status_result = json.loads(status_completed.stdout)
        diff_result = json.loads(diff_completed.stdout)
        revert_result = json.loads(revert_completed.stdout)
        revert_write_result = json.loads(revert_write_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        self.assertEqual(
            [event["event_type"] for event in journal_events],
            [
                "page_create",
                "page_create",
                "section_append",
                "log_append",
                "event_revert",
                "page_update",
                "event_revert",
            ],
        )
        self.assertIn("\n## Updates\n- detail [[B]]\n", page_text)
        self.assertNotIn("- rewritten [[C]]", page_text)
        self.assertEqual(log_text, "# Log\n")
        self.assertEqual(section_result["edge_count"], 1)
        self.assertEqual(section_result["projection"]["written_files"], ["A.md"])
        self.assertEqual(log_result["projection"]["written_files"], ["Log.md"])
        self.assertEqual(write_result["source_path"], "A.md")
        self.assertEqual(write_result["edge_count"], 1)
        self.assertEqual(write_result["projection"]["written_files"], ["A.md"])
        self.assertEqual(status_result["journal_event_count"], 4)
        self.assertTrue(status_result["projection"]["ok"])
        self.assertTrue(status_result["strict_ok"])
        self.assertEqual(status_result["strict_failures"], [])
        self.assertFalse(status_result["journal_log_stale"])
        self.assertEqual(status_result["journal_log_changed_files"], [])
        self.assertTrue(status_result["journal_log_projection"]["ok"])
        self.assertEqual(status_result["journal_log_projection"]["regenerated_files"], ["Log.md"])
        self.assertTrue(diff_result["ok"])
        self.assertEqual(diff_result["diff_count"], 0)
        self.assertEqual(revert_result["target_event_type"], "log_append")
        self.assertEqual(revert_result["projection"]["written_files"], ["Log.md"])
        self.assertEqual(revert_result["removed_line_count"], 3)
        self.assertEqual(revert_write_result["target_event_type"], "page_update")
        self.assertEqual(revert_write_result["restored_line_count"], 4)
        self.assertTrue(replay_result["ok"])
        self.assertEqual(replay_result["file_count"], 2)

    def test_write_status_reports_stale_log_after_direct_markdown_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "append-log",
                    "--timestamp",
                    "2026-06-26 02:00",
                    "--op",
                    "test",
                    "--summary",
                    "journal entry",
                    "--line",
                    "- journal line",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            (root / "Log.md").write_text(
                "# Log\n\n## [2026-06-26 02:00] test | manual replacement\n- not in journal\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            status_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-status",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                    "--strict",
                ],
                text=True,
                capture_output=True,
            )

        status_result = json.loads(status_completed.stdout)
        self.assertEqual(status_completed.returncode, 1)
        self.assertTrue(status_result["projection"]["ok"])
        self.assertFalse(status_result["strict_ok"])
        self.assertEqual([failure["type"] for failure in status_result["strict_failures"]], ["journal_log_stale"])
        self.assertTrue(status_result["journal_log_stale"])
        self.assertEqual(status_result["journal_log_changed_files"], ["Log.md"])
        self.assertFalse(status_result["journal_log_projection"]["ok"])
        self.assertEqual(status_result["journal_log_projection"]["changed_files"], ["Log.md"])
        self.assertEqual(status_result["journal_log_projection"]["regenerated_files"], ["Log.md"])

    def test_write_status_does_not_mark_log_stale_for_non_log_projection_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "append-log",
                    "--timestamp",
                    "2026-06-26 02:10",
                    "--op",
                    "test",
                    "--summary",
                    "journal entry",
                    "--line",
                    "- journal line",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            (root / "A.md").write_text("# A\n- direct non-log edit\n", encoding="utf-8")
            status_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-status",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                    "--strict",
                ],
                text=True,
                capture_output=True,
            )

        status_result = json.loads(status_completed.stdout)
        self.assertEqual(status_completed.returncode, 1)
        self.assertFalse(status_result["projection"]["ok"])
        self.assertEqual(status_result["projection"]["changed_files"], ["A.md"])
        self.assertFalse(status_result["strict_ok"])
        self.assertEqual([failure["type"] for failure in status_result["strict_failures"]], ["projection_dirty"])
        self.assertFalse(status_result["journal_log_stale"])
        self.assertEqual(status_result["journal_log_changed_files"], [])
        self.assertFalse(status_result["journal_log_projection"]["ok"])
        self.assertEqual(status_result["journal_log_projection"]["changed_files"], ["A.md"])

    def test_write_status_strict_fails_when_journal_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            missing_journal_path = Path(tmpdir) / "wiki.grasp" / "missing.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            status_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-status",
                    "--output",
                    str(root),
                    "--journal",
                    str(missing_journal_path),
                    "--strict",
                ],
                text=True,
                capture_output=True,
            )

        status_result = json.loads(status_completed.stdout)
        self.assertEqual(status_completed.returncode, 1)
        self.assertTrue(status_result["projection"]["ok"])
        self.assertFalse(status_result["journal_exists"])
        self.assertFalse(status_result["strict_ok"])
        self.assertEqual([failure["type"] for failure in status_result["strict_failures"]], ["journal_missing"])

    def test_rename_page_preserves_old_handle_and_replays(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nlink [[Old]]\n", encoding="utf-8")
            (root / "Old.md").write_text("# Old\nbody\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            rename_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "rename-page",
                    "Old",
                    "New",
                    "--new-path",
                    "New.md",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            rename_result = json.loads(rename_completed.stdout)
            reimport_store_path = Path(tmpdir) / "reimport.sqlite"
            read_old_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "Old",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            replay_after_rename_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            new_text_during_rename = (root / "New.md").read_text(encoding="utf-8")
            old_exists_during_rename = (root / "Old.md").exists()
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            reimport_read_old_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "--project",
                    "wiki",
                    "read",
                    "Old",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            reimport_check_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            revert_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "revert-event",
                    rename_result["event_id"],
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            replay_after_revert_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            old_exists_after_revert = (root / "Old.md").exists()
            new_exists_after_revert = (root / "New.md").exists()

        read_old_result = json.loads(read_old_completed.stdout)
        replay_after_rename = json.loads(replay_after_rename_completed.stdout)
        reimport_read_old = json.loads(reimport_read_old_completed.stdout)
        reimport_check = json.loads(reimport_check_completed.stdout)
        revert_result = json.loads(revert_completed.stdout)
        replay_after_revert = json.loads(replay_after_revert_completed.stdout)
        self.assertEqual(
            [event["event_type"] for event in journal_events],
            ["page_create", "page_create", "page_rename", "event_revert"],
        )
        self.assertEqual(rename_result["previous_title"], "Old")
        self.assertEqual(rename_result["title"], "New")
        self.assertEqual(rename_result["event_type"], "page_rename")
        self.assertEqual(rename_result["previous_source_path"], "Old.md")
        self.assertEqual(rename_result["source_path"], "New.md")
        self.assertTrue(rename_result["heading_updated"])
        self.assertEqual(rename_result["projection"]["written_files"], ["New.md"])
        self.assertEqual(rename_result["projection"]["removed_files"], ["Old.md"])
        self.assertEqual(
            new_text_during_rename,
            "\n".join(
                [
                    "---",
                    f"id: {rename_result['page']['id']}",
                    "title: New",
                    "aliases:",
                    "  - Old",
                    "---",
                    "# New",
                    "body",
                    "",
                ]
            ),
        )
        self.assertFalse(old_exists_during_rename)
        self.assertEqual(read_old_result["page"]["title"], "New")
        self.assertEqual(read_old_result["backlink_count_total"], 1)
        self.assertTrue(replay_after_rename["ok"])
        self.assertEqual(reimport_read_old["page"]["id"], rename_result["page"]["id"])
        self.assertEqual(reimport_read_old["page"]["title"], "New")
        self.assertEqual(reimport_read_old["backlink_count_total"], 1)
        self.assertTrue(reimport_check["ok"])
        self.assertEqual(revert_result["target_event_type"], "page_rename")
        self.assertEqual(revert_result["restored_line_count"], 2)
        self.assertTrue(old_exists_after_revert)
        self.assertFalse(new_exists_after_revert)
        self.assertTrue(replay_after_revert["ok"])

    def test_read_markdown_page_by_source_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "source").mkdir()
            (root / "source" / "Digest.md").write_text("# Digest\nlinks to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "--path",
                    "source/Digest.md",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["page"]["title"], "Digest")
        self.assertEqual(result["link_stats"]["page_exists"], True)

    def test_import_markdown_folder_excludes_named_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "raw").mkdir()
            (root / "raw" / "Raw.md").write_text("# Raw\nraw-only links to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--markdown-exclude-dir",
                    "raw",
                    "--project",
                    "wiki",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            search_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "search",
                    "raw-only",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        import_result = json.loads(import_completed.stdout)
        search_result = json.loads(search_completed.stdout)
        self.assertEqual(import_result["pages"], 1)
        self.assertEqual(search_result["hits"], [])

    def test_import_markdown_collision_json_error_is_structured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("---\nid: same-id\n---\n# A\n", encoding="utf-8")
            (root / "B.md").write_text("---\nid: same-id\n---\n# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        result = json.loads(completed.stderr)
        self.assertEqual(result["diagnostic"]["type"], "markdown_collision")
        self.assertEqual(result["diagnostic"]["collision_counts"], {"id": 1})
        self.assertEqual(set(result["diagnostic"]["collisions"][0]["paths"]), {"A.md", "B.md"})

    def test_cross_project_refs_writes_acquire_seed_files(self):
        fixture = {
            "name": "nishio",
            "displayName": "nishio",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "A",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 1,
                    "views": 100,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "refs [/villagepump/Page A] and [/villagepump/nishio.icon]", "created": 1, "updated": 1, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            seed_dir = Path(tmpdir) / "seeds"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "nishio",
                    "cross-project-refs",
                    "--semantic-only",
                    "--limit",
                    "1",
                    "--seed-limit",
                    "1",
                    "--seed-dir",
                    str(seed_dir),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            result = json.loads(completed.stdout)
            seed_file = seed_dir / "villagepump.txt"
            self.assertEqual(seed_file.read_text(encoding="utf-8"), "Page A\n")
            self.assertEqual(result["acquire_plan"]["seed_files_written"], 1)
            recipe = result["projects"][0]["acquire_recipe"]
            self.assertTrue(recipe["seed_file_written"])
            self.assertEqual(recipe["seed_file"], str(seed_file))
            self.assertEqual(
                recipe["command"],
                [
                    "grasp",
                    "--project",
                    "villagepump:semantic",
                    "acquire",
                    "https://scrapbox.io/villagepump/",
                    "--seed-file",
                    str(seed_file),
                    "--limit",
                    "1",
                ],
            )

    def test_cross_project_acquire_dry_run_returns_plan(self):
        fixture = {
            "name": "nishio",
            "displayName": "nishio",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "A",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 1,
                    "views": 100,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "refs [/villagepump/PageA] and [/villagepump/PageB]", "created": 1, "updated": 1, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "import",
                    "--cosense",
                    str(export_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "nishio",
                    "cross-project-acquire",
                    "--limit",
                    "1",
                    "--seed-limit",
                    "2",
                    "--acquire-limit",
                    "2",
                    "--dry-run",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            result = json.loads(completed.stdout)
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["summary"]["planned_projects"], 1)
            self.assertEqual(result["summary"]["attempted_projects"], 0)
            project = result["projects"][0]
            self.assertEqual(project["project"], "villagepump")
            self.assertEqual(project["local_project"], "villagepump:semantic")
            self.assertEqual(project["seed_titles"], ["PageA", "PageB"])
            self.assertEqual(project["command"][-2:], ["--limit", "2"])


if __name__ == "__main__":
    unittest.main()
