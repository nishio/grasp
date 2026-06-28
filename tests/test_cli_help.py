import json
import os
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
    "revert-event",
    "revert-events",
    "revert-plan",
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


def init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, text=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, text=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=grasp-test",
            "-c",
            "user.email=grasp-test@example.invalid",
            "commit",
            "-m",
            "initial",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )


class CliHelpTests(unittest.TestCase):
    def test_root_help_declares_mechanics_ssot(self):
        help_text = run_grasp_help()
        self.assertIn("Mechanics SSoT", help_text)
        self.assertIn("--json is also", help_text)
        self.assertIn("--full-ids", help_text)
        self.assertIn("--version", help_text)
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        adopt_result = json.loads(adopt_completed.stdout)
        check_result = json.loads(check_completed.stdout)
        dirty_result = json.loads(dirty_completed.stdout)

        self.assertEqual(adopt_result["journal_events"], 2)
        self.assertEqual(adopt_result["sqlite_events_inserted"], 2)
        self.assertEqual(adopt_result["sqlite_events_skipped"], 0)
        self.assertEqual(adopt_result["adopted_pages"], 2)
        self.assertEqual([event["event_type"] for event in journal_events], ["page_create", "page_create"])
        self.assertEqual(journal_events[0]["project"], "wiki")
        self.assertIn("lines", journal_events[0]["payload"])
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_create", "page_create"])
        self.assertEqual([row[0] for row in sqlite_event_rows], [event["event_id"] for event in journal_events])
        self.assertEqual(json.loads(sqlite_event_rows[0][3])["source_path"], "A.md")
        self.assertTrue(check_result["ok"])
        self.assertEqual(
            check_result["projection_policy"],
            {
                "authority": "sqlite",
                "base": "stored_markdown_lines",
                "output_role": "git_tracked_projection",
                "write_mode": "check",
                "generated_overlays": [],
            },
        )
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        adopt_result = json.loads(adopt_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        status_result = json.loads(status_completed.stdout)
        log_events = [event for event in journal_events if event["event_type"] == "log_entry_import"]
        self.assertEqual(adopt_result["adopted_pages"], 2)
        self.assertEqual(adopt_result["log_entry_records"], 2)
        self.assertEqual(adopt_result["journal_events"], 4)
        self.assertEqual(adopt_result["sqlite_events_inserted"], 4)
        self.assertEqual(adopt_result["sqlite_events_skipped"], 0)
        self.assertEqual(
            [event["event_type"] for event in journal_events],
            ["page_create", "page_create", "log_entry_import", "log_entry_import"],
        )
        self.assertEqual(
            [row[1] for row in sqlite_event_rows],
            ["page_create", "page_create", "log_entry_import", "log_entry_import"],
        )
        self.assertEqual([row[0] for row in sqlite_event_rows], [event["event_id"] for event in journal_events])
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

    def test_log_records_and_history_query_sqlite_events_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            log_path = root / "Log.md"
            (root / "Alpha.md").write_text("# Alpha\n", encoding="utf-8")
            log_path.write_text("# Log\n", encoding="utf-8")
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
                "# Log\n\n"
                "## [2026-06-26 01:00] implementation | first entry\n"
                "- touched [[Alpha]]\n",
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
            log_records_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "log-records",
                    "--journal",
                    str(journal_path),
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
                    str(store_path),
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
            history_text_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_type, project, payload_json
                    FROM events
                    WHERE event_type = 'log_entry_import'
                    ORDER BY event_sequence
                    """
                ).fetchall()
                sqlite_page_rows = connection.execute(
                    "SELECT id, title FROM pages WHERE project = 'wiki' ORDER BY title"
                ).fetchall()
            finally:
                connection.close()

        import_result = json.loads(import_completed.stdout)
        log_records_result = json.loads(log_records_completed.stdout)
        history_result = json.loads(history_completed.stdout)
        history_text = history_text_completed.stdout
        alpha_page_id = next(row[0] for row in sqlite_page_rows if row[1] == "Alpha")
        self.assertEqual(import_result["imported_records"], 1)
        self.assertEqual(import_result["sqlite_events_inserted"], 1)
        self.assertEqual([row[0] for row in sqlite_event_rows], ["log_entry_import"])
        self.assertEqual(sqlite_event_rows[0][1], "wiki")
        self.assertEqual(json.loads(sqlite_event_rows[0][2])["summary"], "first entry")
        self.assertEqual(log_records_result["event_source"], "sqlite")
        self.assertEqual(log_records_result["result_mode"], "event-stream")
        self.assertFalse(log_records_result["current_state"])
        self.assertIsNone(log_records_result["current_state_hint"])
        self.assertIsNone(log_records_result["current_state_target"])
        self.assertEqual(log_records_result["staleness_signals"], ["superseded_by", "later_events"])
        self.assertEqual(log_records_result["sqlite_event_count"], 1)
        self.assertEqual(log_records_result["matched_records"], 1)
        self.assertEqual(log_records_result["records"][0]["subjects"], ["Alpha"])
        self.assertEqual(history_result["event_source"], "sqlite")
        self.assertEqual(history_result["result_mode"], "event-stream")
        self.assertFalse(history_result["current_state"])
        self.assertEqual(history_result["current_state_hint"], f"read --page-id {alpha_page_id}")
        self.assertEqual(history_result["current_state_target"]["status"], "resolved_unique")
        self.assertEqual(history_result["current_state_target"]["page"]["page_id"], alpha_page_id)
        self.assertEqual(history_result["current_state_target"]["read_args"], ["read", "--page-id", alpha_page_id])
        self.assertEqual(history_result["staleness_signals"], ["superseded_by", "later_events"])
        self.assertEqual(history_result["matched_records"], 1)
        self.assertEqual(history_result["records"][0]["summary"], "first entry")
        self.assertIn("result_mode: event-stream", history_text)
        self.assertIn("current_state: false", history_text)
        self.assertIn(f"current_state_hint: read --page-id {alpha_page_id}", history_text)
        self.assertIn("current_state_target: resolved_unique", history_text)
        self.assertIn(f"current_state_read: read --page-id {alpha_page_id}", history_text)

    def test_history_current_state_target_reports_ambiguous_current_projection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("---\naliases: [Shared]\n---\n# A\n", encoding="utf-8")
            (root / "B.md").write_text("---\naliases: [Shared]\n---\n# B\n", encoding="utf-8")
            (root / "Log.md").write_text(
                "# Log\n\n"
                "## [2026-06-26 01:00] implementation | shared entry\n"
                "- touched [[Shared]]\n",
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
            history_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "history",
                    "Shared",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            history_text_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "history",
                    "Shared",
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        history_result = json.loads(history_completed.stdout)
        history_text = history_text_completed.stdout
        target = history_result["current_state_target"]
        self.assertEqual(history_result["matched_records"], 1)
        self.assertEqual(history_result["current_state_hint"], "choose from current_state_target.candidates[].read_args")
        self.assertEqual(target["status"], "ambiguous")
        self.assertEqual(target["candidate_count"], 2)
        self.assertEqual({candidate["title"] for candidate in target["candidates"]}, {"A", "B"})
        self.assertEqual({candidate["path"] for candidate in target["candidates"]}, {"A.md", "B.md"})
        for candidate in target["candidates"]:
            self.assertEqual(candidate["read_args"][:2], ["read", "--page-id"])
            self.assertIn("read --page-id ", candidate["read_command"])
        self.assertIn("current_state_target: ambiguous", history_text)
        self.assertIn("current_state_candidates: 2", history_text)
        self.assertIn("read=read --page-id", history_text)

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
                    str(store_path),
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
                    str(store_path),
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
        self.assertEqual(history_alpha["event_source"], "sqlite")
        self.assertEqual(history_alpha["sqlite_event_count"], 1)
        self.assertEqual(history_alpha["matched_records"], 1)
        self.assertEqual(history_alpha["records"][0]["subjects"], ["Alpha", "Beta"])
        self.assertEqual(history_gamma["event_source"], "sqlite")
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
        self.assertEqual(newest_result["event_source"], "journal")
        self.assertIsNone(newest_result["store"])
        self.assertEqual(newest_result["sqlite_event_count"], 0)
        self.assertEqual(newest_result["total_records"], 2)
        self.assertEqual(newest_result["returned_records"], 1)
        self.assertEqual(newest_result["records"][0]["summary"], "second entry")
        self.assertEqual(newest_result["records"][0]["subjects"], ["Alpha"])
        self.assertEqual(filtered_result["matched_records"], 1)
        self.assertEqual(filtered_result["records"][0]["summary"], "first entry")
        self.assertEqual(filtered_result["records"][0]["body_text"], "- PR #1 touched [[Alpha]]")
        self.assertEqual(filtered_result["records"][0]["subjects"], ["Alpha"])
        self.assertEqual(history_result["query"], "Alpha")
        self.assertEqual(history_result["current_state_hint"], "read Alpha")
        self.assertEqual(history_result["current_state_target"]["status"], "unavailable")
        self.assertEqual(history_result["current_state_target"]["reason"], "store_unavailable")
        self.assertEqual(history_result["current_state_target"]["read_args"], ["read", "Alpha"])
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
        self.assertEqual(write_result["projection_policy"]["authority"], "sqlite")
        self.assertEqual(write_result["projection_policy"]["write_mode"], "write")
        self.assertEqual(
            write_result["projection_policy"]["generated_overlays"],
            ["legacy-journal-log", "navigation-index"],
        )
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
        self.assertEqual(status_completed.returncode, 1)
        self.assertFalse(status_result["strict_ok"])
        self.assertEqual([failure["type"] for failure in status_result["strict_failures"]], ["semantic_log_stale"])
        self.assertTrue(status_result["journal_log_projection"]["ok"])
        self.assertTrue(status_result["semantic_log_stale"])
        self.assertEqual(status_result["semantic_log_changed_files"], ["Log.md"])
        self.assertEqual(
            log_text,
            "# Log\n\n"
            "## [2026-06-26 03:00] decision | projected record updated\n"
            "- second body [[Beta]]\n",
        )
        self.assertNotIn("first body", log_text)

    def test_export_markdown_regenerates_log_from_sqlite_events_without_journal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            log_dir = root / "log"
            log_dir.mkdir(parents=True)
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            (root / "Alpha.md").write_text("# Alpha\n", encoding="utf-8")
            (log_dir / "entry.md").write_text(
                "---\n"
                "type: log-entry\n"
                "date: 2026-06-26 03:00\n"
                "op: decision\n"
                "summary: sqlite projected record\n"
                "subjects:\n"
                "  - Alpha\n"
                "---\n"
                "# sqlite projected record\n\n"
                "- body from sqlite [[Alpha]]\n",
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
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            log_text = (root / "Log.md").read_text(encoding="utf-8")

        dirty_result = json.loads(dirty_completed.stdout)
        write_result = json.loads(write_completed.stdout)
        self.assertEqual(dirty_completed.returncode, 1)
        self.assertEqual(dirty_result["log_event_source"], "sqlite")
        self.assertGreater(dirty_result["log_event_count"], 0)
        self.assertEqual(dirty_result["changed_files"], ["Log.md"])
        self.assertEqual(write_result["written_files"], ["Log.md"])
        self.assertEqual(
            write_result["projection_policy"]["generated_overlays"],
            ["sqlite-events-log"],
        )
        self.assertEqual(
            log_text,
            "# Log\n\n"
            "## [2026-06-26 03:00] decision | sqlite projected record\n"
            "- body from sqlite [[Alpha]]\n",
        )

    def test_export_markdown_regenerate_log_accepts_sqlite_page_update_seed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            replacement = Path(tmpdir) / "replacement.md"
            replacement.write_text(
                "# Log\n\n"
                "## [2026-06-26 04:00] test | update seed\n"
                "- from page update\n",
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
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-page",
                    "Log",
                    "--from-file",
                    str(replacement),
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
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
                    "--check",
                ],
                text=True,
                capture_output=True,
            )

        dirty_result = json.loads(dirty_completed.stdout)
        self.assertEqual(dirty_completed.returncode, 1)
        self.assertEqual(dirty_result["log_event_source"], "sqlite")
        self.assertEqual(dirty_result["projection_policy"]["generated_overlays"], ["sqlite-events-log"])
        self.assertEqual(dirty_result["changed_files"], ["Log.md"])

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
            status_after_create_completed = subprocess.run(
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_revert = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            status_after_revert_completed = subprocess.run(
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
        status_after_create = json.loads(status_after_create_completed.stdout)
        read_result = json.loads(read_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        revert_result = json.loads(revert_completed.stdout)
        status_after_revert = json.loads(status_after_revert_completed.stdout)
        replay_after_revert = json.loads(replay_after_revert_completed.stdout)
        self.assertEqual([event["event_type"] for event in journal_events], ["page_create", "page_create", "event_revert"])
        self.assertEqual(len(sqlite_event_rows), 2)
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_create", "page_create"])
        self.assertEqual(sqlite_event_rows[0][0], journal_events[0]["event_id"])
        self.assertEqual(sqlite_event_rows[1][0], create_result["event_id"])
        self.assertEqual(sqlite_event_rows[1][2], "wiki")
        self.assertEqual(json.loads(sqlite_event_rows[1][3])["source_path"], "New.md")
        self.assertEqual(status_after_create["journal_event_count"], 2)
        self.assertEqual(status_after_create["last_event"]["event_id"], create_result["event_id"])
        self.assertEqual(status_after_create["sqlite_event_count"], 2)
        self.assertEqual(status_after_create["sqlite_last_event"]["event_id"], create_result["event_id"])
        self.assertEqual(status_after_create["sqlite_last_event"]["event_type"], "page_create")
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
        self.assertEqual(revert_result["target_event_source"], "sqlite")
        self.assertEqual(revert_result["removed_line_count"], 2)
        self.assertEqual(revert_result["projection"]["removed_files"], ["New.md"])
        self.assertEqual([row[1] for row in sqlite_event_rows_after_revert], ["page_create", "page_create", "event_revert"])
        self.assertEqual(sqlite_event_rows_after_revert[2][0], revert_result["event_id"])
        sqlite_revert_payload = json.loads(sqlite_event_rows_after_revert[2][3])
        self.assertEqual(sqlite_revert_payload["target_event_id"], create_result["event_id"])
        self.assertEqual(status_after_revert["sqlite_event_count"], 3)
        self.assertEqual(status_after_revert["sqlite_last_event"]["event_id"], revert_result["event_id"])
        self.assertEqual(status_after_revert["sqlite_last_event"]["event_type"], "event_revert")
        self.assertFalse(new_exists_after_revert)
        self.assertTrue(replay_after_revert["ok"])

    def test_revert_event_dry_run_reports_revertible_without_mutating_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
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
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            create_result = json.loads(create_completed.stdout)
            dry_run_completed = subprocess.run(
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
                    create_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
                    "--dry-run",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            new_text = (root / "New.md").read_text(encoding="utf-8")

        dry_run_result = json.loads(dry_run_completed.stdout)
        read_result = json.loads(read_completed.stdout)
        self.assertTrue(dry_run_result["dry_run"])
        self.assertTrue(dry_run_result["revertible"])
        self.assertIsNone(dry_run_result["event_id"])
        self.assertEqual(dry_run_result["would_event_type"], "event_revert")
        self.assertFalse(dry_run_result["journal_written"])
        self.assertFalse(dry_run_result["would_write_journal"])
        self.assertTrue(dry_run_result["would_export_projection"])
        self.assertEqual(dry_run_result["would_remove_files"], ["New.md"])
        self.assertEqual(dry_run_result["target_event_id"], create_result["event_id"])
        self.assertEqual(dry_run_result["target_event_type"], "page_create")
        self.assertEqual(dry_run_result["target_event_source"], "sqlite")
        self.assertEqual(dry_run_result["removed_line_count"], 2)
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_create"])
        self.assertEqual(sqlite_event_rows[0][0], create_result["event_id"])
        self.assertEqual(read_result["page"]["title"], "New")
        self.assertEqual(new_text, "# New\nbody [[A]]\n")

    def test_revert_event_dry_run_reports_non_revertible_dependency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
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
            first_completed = subprocess.run(
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
                    "First",
                    "--line",
                    "- first",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            second_completed = subprocess.run(
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
                    "Second",
                    "--line",
                    "- second",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            first_result = json.loads(first_completed.stdout)
            second_result = json.loads(second_completed.stdout)
            dry_run_completed = subprocess.run(
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
                    first_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
                    "--dry-run",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            page_text = (root / "A.md").read_text(encoding="utf-8")

        dry_run_result = json.loads(dry_run_completed.stdout)
        self.assertTrue(dry_run_result["dry_run"])
        self.assertFalse(dry_run_result["revertible"])
        self.assertIsNone(dry_run_result["event_id"])
        self.assertEqual(dry_run_result["target_event_id"], first_result["event_id"])
        self.assertEqual(dry_run_result["target_event_type"], "section_append")
        self.assertEqual(dry_run_result["target_event_source"], "sqlite")
        self.assertIn("event is not at the page tail", dry_run_result["reason"])
        self.assertFalse(dry_run_result["would_export_projection"])
        self.assertEqual(dry_run_result["would_remove_files"], [])
        self.assertEqual([row[0] for row in sqlite_event_rows], [first_result["event_id"], second_result["event_id"]])
        self.assertEqual([row[1] for row in sqlite_event_rows], ["section_append", "section_append"])
        self.assertIn("- first", page_text)
        self.assertIn("- second", page_text)

    def test_revert_event_include_dependents_reverts_later_same_page_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
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
            first_completed = subprocess.run(
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
                    "First",
                    "--line",
                    "- first",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            second_completed = subprocess.run(
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
                    "Second",
                    "--line",
                    "- second",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            first_result = json.loads(first_completed.stdout)
            second_result = json.loads(second_completed.stdout)
            dry_run_completed = subprocess.run(
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
                    first_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
                    "--dry-run",
                    "--include-dependents",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_dry_run = connection.execute(
                    """
                    SELECT event_id, event_type, project
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            page_text_after_dry_run = (root / "A.md").read_text(encoding="utf-8")
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
                    first_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
                    "--include-dependents",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_revert = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            page_text_after_revert = (root / "A.md").read_text(encoding="utf-8")

        dry_run_result = json.loads(dry_run_completed.stdout)
        revert_result = json.loads(revert_completed.stdout)
        self.assertTrue(dry_run_result["dry_run"])
        self.assertTrue(dry_run_result["revertible"])
        self.assertIsNone(dry_run_result["event_id"])
        self.assertEqual(dry_run_result["event_ids"], [])
        self.assertEqual(dry_run_result["target_event_id"], first_result["event_id"])
        self.assertEqual(dry_run_result["target_event_type"], "section_append")
        self.assertEqual(dry_run_result["included_dependent_event_ids"], [second_result["event_id"]])
        self.assertEqual(dry_run_result["included_dependent_count"], 1)
        self.assertEqual(dry_run_result["would_event_count"], 2)
        self.assertEqual(
            [event["target_event_id"] for event in dry_run_result["reverted_events"]],
            [second_result["event_id"], first_result["event_id"]],
        )
        self.assertTrue(dry_run_result["would_export_projection"])
        self.assertEqual(dry_run_result["would_remove_files"], [])
        self.assertEqual([row[1] for row in sqlite_event_rows_after_dry_run], ["section_append", "section_append"])
        self.assertIn("- first", page_text_after_dry_run)
        self.assertIn("- second", page_text_after_dry_run)
        self.assertFalse(revert_result["dry_run"])
        self.assertTrue(revert_result["revertible"])
        self.assertEqual(revert_result["target_event_id"], first_result["event_id"])
        self.assertEqual(revert_result["target_event_type"], "section_append")
        self.assertEqual(revert_result["included_dependent_event_ids"], [second_result["event_id"]])
        self.assertEqual(revert_result["included_dependent_count"], 1)
        self.assertEqual(revert_result["reverted_event_count"], 2)
        self.assertEqual(len(revert_result["event_ids"]), 2)
        self.assertEqual(revert_result["event_id"], revert_result["event_ids"][-1])
        self.assertEqual(
            [event["target_event_id"] for event in revert_result["reverted_events"]],
            [second_result["event_id"], first_result["event_id"]],
        )
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_revert],
            ["section_append", "section_append", "event_revert", "event_revert"],
        )
        self.assertEqual(
            [json.loads(row[3])["target_event_id"] for row in sqlite_event_rows_after_revert[2:]],
            [second_result["event_id"], first_result["event_id"]],
        )
        self.assertEqual(page_text_after_revert, "# A\n")

    def test_revert_event_include_dependents_handles_create_then_rename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nlink [[Old]]\n", encoding="utf-8")
            source = Path(tmpdir) / "OldSource.md"
            source.write_text("# Old\nbody\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            create_result = run_json(
                "write-page",
                "Old",
                "--create",
                "--path",
                "Old.md",
                "--from-file",
                str(source),
                "--output",
                str(root),
                "--no-journal",
            )
            rename_result = run_json(
                "rename-page",
                "Old",
                "New",
                "--new-path",
                "New.md",
                "--output",
                str(root),
                "--no-journal",
            )
            dry_run_result = run_json(
                "revert-event",
                create_result["event_id"],
                "--output",
                str(root),
                "--no-journal",
                "--dry-run",
                "--include-dependents",
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_dry_run = connection.execute(
                    """
                    SELECT event_id, event_type, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            files_after_dry_run = sorted(path.name for path in root.iterdir() if path.is_file())
            revert_result = run_json(
                "revert-event",
                create_result["event_id"],
                "--output",
                str(root),
                "--no-journal",
                "--include-dependents",
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_revert = connection.execute(
                    """
                    SELECT event_id, event_type, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            files_after_revert = sorted(path.name for path in root.iterdir() if path.is_file())
            a_text_after_revert = (root / "A.md").read_text(encoding="utf-8")

        self.assertTrue(dry_run_result["dry_run"])
        self.assertTrue(dry_run_result["revertible"])
        self.assertEqual(dry_run_result["target_event_id"], create_result["event_id"])
        self.assertEqual(dry_run_result["target_event_type"], "page_create")
        self.assertEqual(dry_run_result["included_dependent_event_ids"], [rename_result["event_id"]])
        self.assertEqual(
            [event["target_event_type"] for event in dry_run_result["reverted_events"]],
            ["page_rename", "page_create"],
        )
        self.assertEqual(dry_run_result["would_remove_files"], ["New.md"])
        self.assertEqual([row[1] for row in sqlite_event_rows_after_dry_run], ["page_create", "page_rename"])
        self.assertEqual(files_after_dry_run, ["A.md", "New.md"])
        self.assertFalse(revert_result["dry_run"])
        self.assertEqual(revert_result["target_event_id"], create_result["event_id"])
        self.assertEqual(revert_result["target_event_type"], "page_create")
        self.assertEqual(revert_result["included_dependent_event_ids"], [rename_result["event_id"]])
        self.assertEqual(revert_result["reverted_event_count"], 2)
        self.assertEqual(
            [event["target_event_type"] for event in revert_result["reverted_events"]],
            ["page_rename", "page_create"],
        )
        self.assertEqual(revert_result["projection"]["removed_files"], ["New.md"])
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_revert],
            ["page_create", "page_rename", "event_revert", "event_revert"],
        )
        self.assertEqual(
            [json.loads(row[2])["target_event_id"] for row in sqlite_event_rows_after_revert[2:]],
            [rename_result["event_id"], create_result["event_id"]],
        )
        self.assertEqual(files_after_revert, ["A.md"])
        self.assertEqual(a_text_after_revert, "# A\nlink [[Old]]\n")

    def test_revert_events_reverts_explicit_multi_page_events_in_reverse_sequence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            b_source = Path(tmpdir) / "B-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            dry_run_result = run_json(
                "revert-events",
                a_update["event_id"],
                b_update["event_id"],
                "--output",
                str(root),
                "--no-journal",
                "--dry-run",
            )
            a_text_after_dry_run = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_dry_run = (root / "B.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_dry_run = connection.execute(
                    """
                    SELECT event_id, event_type, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            revert_result = run_json(
                "revert-events",
                a_update["event_id"],
                b_update["event_id"],
                "--output",
                str(root),
                "--no-journal",
            )
            a_text_after_revert = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_revert = (root / "B.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_revert = connection.execute(
                    """
                    SELECT event_id, event_type, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertTrue(dry_run_result["dry_run"])
        self.assertTrue(dry_run_result["revertible"])
        self.assertEqual(dry_run_result["requested_event_ids"], [a_update["event_id"], b_update["event_id"]])
        self.assertEqual(dry_run_result["revert_order_event_ids"], [b_update["event_id"], a_update["event_id"]])
        self.assertEqual(dry_run_result["would_event_count"], 2)
        self.assertEqual(dry_run_result["event_ids"], [])
        self.assertEqual(
            [event["target_event_id"] for event in dry_run_result["reverted_events"]],
            [b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(a_text_after_dry_run, "# A\nnew A\n")
        self.assertEqual(b_text_after_dry_run, "# B\nnew B\n")
        self.assertEqual([row[1] for row in sqlite_event_rows_after_dry_run], ["page_update", "page_update"])
        self.assertFalse(revert_result["dry_run"])
        self.assertTrue(revert_result["revertible"])
        self.assertEqual(revert_result["requested_event_ids"], [a_update["event_id"], b_update["event_id"]])
        self.assertEqual(revert_result["revert_order_event_ids"], [b_update["event_id"], a_update["event_id"]])
        self.assertEqual(revert_result["target_event_ids"], [b_update["event_id"], a_update["event_id"]])
        self.assertEqual(revert_result["reverted_event_count"], 2)
        self.assertEqual(len(revert_result["event_ids"]), 2)
        self.assertEqual(
            [event["target_event_id"] for event in revert_result["reverted_events"]],
            [b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(a_text_after_revert, "# A\nold A\n")
        self.assertEqual(b_text_after_revert, "# B\nold B\n")
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_revert],
            ["page_update", "page_update", "event_revert", "event_revert"],
        )
        self.assertEqual(
            [json.loads(row[2])["target_event_id"] for row in sqlite_event_rows_after_revert[2:]],
            [b_update["event_id"], a_update["event_id"]],
        )

    def test_revert_plan_log_batch_infers_file_back_work_unit_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            b_source = Path(tmpdir) / "B-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            first_log = run_json(
                "append-log",
                "--timestamp",
                "2026-06-27 01:00",
                "--op",
                "test",
                "--summary",
                "previous batch",
                "--line",
                "- previous",
                "--output",
                str(root),
                "--no-journal",
            )
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            closing_log = run_json(
                "append-log",
                "--timestamp",
                "2026-06-27 02:00",
                "--op",
                "test",
                "--summary",
                "target batch",
                "--line",
                "- done",
                "--output",
                str(root),
                "--no-journal",
            )
            plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "log-batch",
                "--output",
                str(root),
            )
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_plan = (root / "B.md").read_text(encoding="utf-8")
            log_text_after_plan = (root / "Log.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_plan = connection.execute(
                    """
                    SELECT event_id, event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertEqual(plan["previous_log_event"]["event_id"], first_log["event_id"])
        self.assertEqual(plan["closing_log_event"]["event_id"], closing_log["event_id"])
        self.assertEqual(
            plan["candidate_event_ids"],
            [a_update["event_id"], b_update["event_id"], closing_log["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [closing_log["event_id"], b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            [event["event_type"] for event in plan["candidate_events"]],
            ["page_update", "page_update", "log_append"],
        )
        self.assertEqual(plan["excluded_events"], [])
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [closing_log["event_id"], b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            plan["suggested_revert_events_args"],
            [
                "revert-events",
                a_update["event_id"],
                b_update["event_id"],
                closing_log["event_id"],
                "--output",
                str(root),
            ],
        )
        self.assertEqual(a_text_after_plan, "# A\nnew A\n")
        self.assertEqual(b_text_after_plan, "# B\nnew B\n")
        self.assertIn("target batch", log_text_after_plan)
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_plan],
            ["log_append", "page_update", "page_update", "log_append"],
        )

    def test_revert_plan_subject_log_filters_mixed_log_batch_by_closing_log_subjects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            (root / "C.md").write_text("# C\nold C\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            b_source = Path(tmpdir) / "B-new.md"
            c_source = Path(tmpdir) / "C-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            c_source.write_text("# C\nnew C\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            previous_log = run_json(
                "append-log",
                "--timestamp",
                "2026-06-27 01:00",
                "--op",
                "test",
                "--summary",
                "previous batch",
                "--line",
                "- previous",
                "--output",
                str(root),
                "--no-journal",
            )
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            c_update = run_json(
                "write-page",
                "C",
                "--from-file",
                str(c_source),
                "--output",
                str(root),
                "--no-journal",
            )
            closing_log = run_json(
                "append-log",
                "--timestamp",
                "2026-06-27 02:00",
                "--op",
                "test",
                "--summary",
                "subject batch for [[A]]",
                "--line",
                "- also touched concepts/C.md",
                "--output",
                str(root),
                "--no-journal",
            )
            log_batch_plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "log-batch",
                "--output",
                str(root),
            )
            subject_plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "subject-log",
                "--output",
                str(root),
            )
            b_anchor_plan = run_json(
                "revert-plan",
                b_update["event_id"],
                "--scope",
                "subject-log",
                "--output",
                str(root),
            )
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_plan = (root / "B.md").read_text(encoding="utf-8")
            c_text_after_plan = (root / "C.md").read_text(encoding="utf-8")
            log_text_after_plan = (root / "Log.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_plan = connection.execute(
                    """
                    SELECT event_id, event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(
            log_batch_plan["candidate_event_ids"],
            [a_update["event_id"], b_update["event_id"], c_update["event_id"], closing_log["event_id"]],
        )
        self.assertEqual(subject_plan["scope"], "subject-log")
        self.assertTrue(subject_plan["complete"])
        self.assertTrue(subject_plan["revertible"])
        self.assertEqual(subject_plan["previous_log_event"]["event_id"], previous_log["event_id"])
        self.assertEqual(subject_plan["closing_log_event"]["event_id"], closing_log["event_id"])
        self.assertEqual(subject_plan["subject_log_subjects"], ["A", "C"])
        self.assertEqual(
            subject_plan["candidate_event_ids"],
            [a_update["event_id"], c_update["event_id"], closing_log["event_id"]],
        )
        self.assertEqual(
            subject_plan["revert_order_event_ids"],
            [closing_log["event_id"], c_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            [event["event_type"] for event in subject_plan["candidate_events"]],
            ["page_update", "page_update", "log_append"],
        )
        self.assertEqual(
            [event["event_id"] for event in subject_plan["excluded_events"]],
            [b_update["event_id"]],
        )
        self.assertIn("does not match closing log subjects", subject_plan["excluded_events"][0]["reason"])
        self.assertEqual(
            [event["target_event_id"] for event in subject_plan["reverted_events"]],
            [closing_log["event_id"], c_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            subject_plan["suggested_revert_events_args"],
            [
                "revert-events",
                a_update["event_id"],
                c_update["event_id"],
                closing_log["event_id"],
                "--output",
                str(root),
            ],
        )
        self.assertFalse(b_anchor_plan["complete"])
        self.assertFalse(b_anchor_plan["revertible"])
        self.assertIn("does not match closing log subjects", b_anchor_plan["reason"])
        self.assertEqual(a_text_after_plan, "# A\nnew A\n")
        self.assertEqual(b_text_after_plan, "# B\nnew B\n")
        self.assertEqual(c_text_after_plan, "# C\nnew C\n")
        self.assertIn("subject batch", log_text_after_plan)
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_plan],
            ["log_append", "page_update", "page_update", "page_update", "log_append"],
        )

    def test_revert_plan_subject_log_includes_required_same_page_dependents_after_closing_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            a_cleanup_source = Path(tmpdir) / "A-cleanup.md"
            b_source = Path(tmpdir) / "B-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            a_cleanup_source.write_text("# A\nnew A\ncleanup\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            closing_log = run_json(
                "append-log",
                "--timestamp",
                "2026-06-28 01:00",
                "--op",
                "test",
                "--summary",
                "subject batch for [[A]]",
                "--line",
                "- B was noise",
                "--output",
                str(root),
                "--no-journal",
            )
            a_cleanup = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_cleanup_source),
                "--output",
                str(root),
                "--no-journal",
            )
            log_batch_plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "log-batch",
                "--output",
                str(root),
            )
            plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "subject-log",
                "--output",
                str(root),
            )
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_plan = (root / "B.md").read_text(encoding="utf-8")
            log_text_after_plan = (root / "Log.md").read_text(encoding="utf-8")

        self.assertEqual(log_batch_plan["scope"], "log-batch")
        self.assertTrue(log_batch_plan["revertible"])
        self.assertEqual(log_batch_plan["dependent_event_ids"], [a_cleanup["event_id"]])
        self.assertEqual(
            log_batch_plan["candidate_event_ids"],
            [a_update["event_id"], b_update["event_id"], closing_log["event_id"], a_cleanup["event_id"]],
        )
        self.assertEqual(
            log_batch_plan["revert_order_event_ids"],
            [a_cleanup["event_id"], closing_log["event_id"], b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(plan["scope"], "subject-log")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertEqual(plan["subject_log_subjects"], ["A"])
        self.assertEqual(plan["dependent_event_ids"], [a_cleanup["event_id"]])
        self.assertEqual(
            plan["candidate_event_ids"],
            [a_update["event_id"], closing_log["event_id"], a_cleanup["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [a_cleanup["event_id"], closing_log["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [a_cleanup["event_id"], closing_log["event_id"], a_update["event_id"]],
        )
        self.assertIn(
            b_update["event_id"],
            [event["event_id"] for event in plan["excluded_events"]],
        )
        self.assertEqual(a_text_after_plan, "# A\nnew A\ncleanup\n")
        self.assertEqual(b_text_after_plan, "# B\nnew B\n")
        self.assertIn("subject batch", log_text_after_plan)

    def test_revert_plan_log_page_subjects_includes_required_same_page_dependents_after_closing_log_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            a_cleanup_source = Path(tmpdir) / "A-cleanup.md"
            b_source = Path(tmpdir) / "B-new.md"
            log_source = Path(tmpdir) / "Log-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            a_cleanup_source.write_text("# A\nnew A\ncleanup\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            log_source.write_text(
                "# Log\n\n## [2026-06-28 01:00] test | subject batch for [[A]]\n- B was noise\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            closing_log = run_json(
                "write-page",
                "Log",
                "--from-file",
                str(log_source),
                "--output",
                str(root),
                "--no-journal",
            )
            a_cleanup = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_cleanup_source),
                "--output",
                str(root),
                "--no-journal",
            )
            plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "log-page-subjects",
                "--output",
                str(root),
            )
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_plan = (root / "B.md").read_text(encoding="utf-8")
            log_text_after_plan = (root / "Log.md").read_text(encoding="utf-8")

        self.assertEqual(plan["scope"], "log-page-subjects")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertEqual(plan["log_page_subjects"], ["A"])
        self.assertEqual(plan["dependent_event_ids"], [a_cleanup["event_id"]])
        self.assertEqual(
            plan["candidate_event_ids"],
            [a_update["event_id"], closing_log["event_id"], a_cleanup["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [a_cleanup["event_id"], closing_log["event_id"], a_update["event_id"]],
        )
        self.assertIn(
            b_update["event_id"],
            [event["event_id"] for event in plan["excluded_events"]],
        )
        self.assertEqual(a_text_after_plan, "# A\nnew A\ncleanup\n")
        self.assertEqual(b_text_after_plan, "# B\nnew B\n")
        self.assertIn("subject batch", log_text_after_plan)

    def test_revert_plan_content_subjects_falls_back_to_anchor_target_for_page_create(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            topic_source = Path(tmpdir) / "Topic.md"
            a_source = Path(tmpdir) / "A-new.md"
            topic_source.write_text("# Topic\nplain body\n", encoding="utf-8")
            a_source.write_text("# A\nold A\n- see [[Topic]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            topic_create = run_json(
                "write-page",
                "Topic",
                "--create",
                "--path",
                "Topic.md",
                "--from-file",
                str(topic_source),
                "--output",
                str(root),
                "--no-journal",
            )
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            closing_log = run_json(
                "append-log",
                "--timestamp",
                "2026-06-28 01:00",
                "--op",
                "test",
                "--summary",
                "created [[Topic]]",
                "--line",
                "- linked from A",
                "--output",
                str(root),
                "--no-journal",
            )
            plan = run_json(
                "revert-plan",
                topic_create["event_id"],
                "--scope",
                "content-subjects",
                "--output",
                str(root),
            )
            topic_text_after_plan = (root / "Topic.md").read_text(encoding="utf-8")
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            log_text_after_plan = (root / "Log.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_plan = connection.execute(
                    """
                    SELECT event_id, event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(plan["scope"], "content-subjects")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertEqual(plan["content_subjects"], [])
        self.assertEqual(plan["content_subject_source"], "anchor-target")
        self.assertIn("topic", plan["content_subject_norms"])
        self.assertEqual(
            plan["candidate_event_ids"],
            [topic_create["event_id"], a_update["event_id"], closing_log["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [closing_log["event_id"], a_update["event_id"], topic_create["event_id"]],
        )
        self.assertEqual(
            [event["event_type"] for event in plan["candidate_events"]],
            ["page_create", "page_update", "log_append"],
        )
        self.assertEqual(plan["excluded_events"], [])
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [closing_log["event_id"], a_update["event_id"], topic_create["event_id"]],
        )
        self.assertEqual(
            plan["suggested_revert_events_args"],
            [
                "revert-events",
                topic_create["event_id"],
                a_update["event_id"],
                closing_log["event_id"],
                "--output",
                str(root),
            ],
        )
        self.assertEqual(topic_text_after_plan, "# Topic\nplain body\n")
        self.assertEqual(a_text_after_plan, "# A\nold A\n- see [[Topic]]\n")
        self.assertIn("created [[Topic]]", log_text_after_plan)
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_plan],
            ["page_create", "page_update", "log_append"],
        )

    def test_revert_plan_content_subjects_includes_required_same_page_dependents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold [[Topic]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nunrelated\n", encoding="utf-8")
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            (root / "Topic.md").write_text("# Topic\n", encoding="utf-8")
            first_source = Path(tmpdir) / "A-first.md"
            first_source.write_text("# A\nnew [[Topic]]\n", encoding="utf-8")
            cleanup_source = Path(tmpdir) / "A-cleanup.md"
            cleanup_source.write_text("# A\nnew [[Topic]]\nlocal cleanup\n", encoding="utf-8")
            b_source = Path(tmpdir) / "B-new.md"
            b_source.write_text("# B\nunrelated edit\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(first_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            a_cleanup = run_json(
                "write-page",
                "A",
                "--from-file",
                str(cleanup_source),
                "--output",
                str(root),
                "--no-journal",
            )
            log_append = run_json(
                "append-log",
                "--op",
                "implementation",
                "--summary",
                "topic update",
                "--line",
                "- changed [[Topic]]",
                "--output",
                str(root),
                "--no-journal",
            )
            projected_before_plan = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(root.glob("*.md"))
            }
            plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "content-subjects",
                "--output",
                str(root),
            )
            projected_after_plan = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(root.glob("*.md"))
            }

        self.assertEqual(plan["scope"], "content-subjects")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertIn("topic", plan["content_subject_norms"])
        self.assertEqual(plan["dependent_event_ids"], [a_cleanup["event_id"]])
        self.assertEqual(
            plan["candidate_event_ids"],
            [a_update["event_id"], a_cleanup["event_id"], log_append["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [log_append["event_id"], a_cleanup["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [log_append["event_id"], a_cleanup["event_id"], a_update["event_id"]],
        )
        self.assertNotIn(
            a_cleanup["event_id"],
            [event["event_id"] for event in plan["excluded_events"]],
        )
        self.assertIn(
            b_update["event_id"],
            [event["event_id"] for event in plan["excluded_events"]],
        )
        self.assertEqual(projected_after_plan, projected_before_plan)

    def test_revert_plan_same_page_dependents_handles_missing_log_batch_boundary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            first_append = run_json(
                "append-section",
                "A",
                "--heading",
                "First",
                "--line",
                "- first",
                "--output",
                str(root),
                "--no-journal",
            )
            second_append = run_json(
                "append-section",
                "A",
                "--heading",
                "Second",
                "--line",
                "- second",
                "--output",
                str(root),
                "--no-journal",
            )
            blocked_without_dependents = run_json(
                "revert-event",
                first_append["event_id"],
                "--output",
                str(root),
                "--no-journal",
                "--dry-run",
            )
            plan = run_json(
                "revert-plan",
                first_append["event_id"],
                "--scope",
                "same-page-dependents",
                "--output",
                str(root),
            )
            page_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_plan = connection.execute(
                    """
                    SELECT event_id, event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertFalse(blocked_without_dependents["revertible"])
        self.assertIn("event is not at the page tail", blocked_without_dependents["reason"])
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertIsNone(plan["previous_log_event"])
        self.assertIsNone(plan["closing_log_event"])
        self.assertEqual(
            plan["candidate_event_ids"],
            [first_append["event_id"], second_append["event_id"]],
        )
        self.assertEqual(plan["dependent_event_ids"], [second_append["event_id"]])
        self.assertEqual(
            plan["revert_order_event_ids"],
            [second_append["event_id"], first_append["event_id"]],
        )
        self.assertEqual(
            [event["event_type"] for event in plan["candidate_events"]],
            ["section_append", "section_append"],
        )
        self.assertEqual(plan["excluded_events"], [])
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [second_append["event_id"], first_append["event_id"]],
        )
        self.assertEqual(
            plan["suggested_revert_events_args"],
            [
                "revert-events",
                first_append["event_id"],
                second_append["event_id"],
                "--output",
                str(root),
            ],
        )
        self.assertIn("- first", page_text_after_plan)
        self.assertIn("- second", page_text_after_plan)
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_plan],
            ["section_append", "section_append"],
        )

    def test_revert_plan_event_window_handles_multi_page_sequence_without_log_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            b_source = Path(tmpdir) / "B-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "event-window",
                "--after",
                "1",
                "--output",
                str(root),
            )
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_plan = (root / "B.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_plan = connection.execute(
                    """
                    SELECT event_id, event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(plan["scope"], "event-window")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertIsNone(plan["previous_log_event"])
        self.assertIsNone(plan["closing_log_event"])
        self.assertEqual(plan["window_before"], 0)
        self.assertEqual(plan["window_after"], 1)
        self.assertEqual(
            plan["candidate_event_ids"],
            [a_update["event_id"], b_update["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            [event["event_type"] for event in plan["candidate_events"]],
            ["page_update", "page_update"],
        )
        self.assertEqual(plan["excluded_events"], [])
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            plan["suggested_revert_events_args"],
            [
                "revert-events",
                a_update["event_id"],
                b_update["event_id"],
                "--output",
                str(root),
            ],
        )
        self.assertEqual(a_text_after_plan, "# A\nnew A\n")
        self.assertEqual(b_text_after_plan, "# B\nnew B\n")
        self.assertEqual([row[1] for row in sqlite_event_rows_after_plan], ["page_update", "page_update"])

    def test_revert_plan_time_burst_infers_multi_page_sequence_without_counting_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            (root / "C.md").write_text("# C\nold C\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            b_source = Path(tmpdir) / "B-new.md"
            c_source = Path(tmpdir) / "C-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            c_source.write_text("# C\nnew C\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args):
                completed = subprocess.run(
                    [sys.executable, "-m", "grasp", "--json", "--store", str(store_path), "--project", "wiki", *args],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
            )
            c_update = run_json(
                "write-page",
                "C",
                "--from-file",
                str(c_source),
                "--output",
                str(root),
                "--no-journal",
            )
            connection = sqlite3.connect(store_path)
            try:
                connection.executemany(
                    """
                    UPDATE events
                    SET created_at = ?
                    WHERE event_id = ?
                    """,
                    [
                        ("2026-06-27T00:00:00+00:00", a_update["event_id"]),
                        ("2026-06-27T00:01:00+00:00", b_update["event_id"]),
                        ("2026-06-27T00:10:00+00:00", c_update["event_id"]),
                    ],
                )
                connection.commit()
            finally:
                connection.close()
            plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "time-burst",
                "--max-gap-seconds",
                "120",
                "--output",
                str(root),
            )
            invalid_gap = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "revert-plan",
                    a_update["event_id"],
                    "--scope",
                    "time-burst",
                    "--max-gap-seconds",
                    "nan",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_plan = (root / "B.md").read_text(encoding="utf-8")
            c_text_after_plan = (root / "C.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_plan = connection.execute(
                    """
                    SELECT event_id, event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(plan["scope"], "time-burst")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertEqual(plan["max_gap_seconds"], 120.0)
        self.assertEqual(
            plan["candidate_event_ids"],
            [a_update["event_id"], b_update["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            [event["event_type"] for event in plan["candidate_events"]],
            ["page_update", "page_update"],
        )
        self.assertEqual(plan["excluded_events"], [])
        self.assertEqual([event["event_id"] for event in plan["boundary_events"]], [c_update["event_id"]])
        self.assertIn("exceeds max_gap_seconds", plan["boundary_events"][0]["reason"])
        self.assertNotEqual(invalid_gap.returncode, 0)
        self.assertIn("finite positive number", invalid_gap.stderr)
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [b_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            plan["suggested_revert_events_args"],
            [
                "revert-events",
                a_update["event_id"],
                b_update["event_id"],
                "--output",
                str(root),
            ],
        )
        self.assertEqual(a_text_after_plan, "# A\nnew A\n")
        self.assertEqual(b_text_after_plan, "# B\nnew B\n")
        self.assertEqual(c_text_after_plan, "# C\nnew C\n")
        self.assertEqual(
            [row[1] for row in sqlite_event_rows_after_plan],
            ["page_update", "page_update", "page_update"],
        )

    def test_revert_plan_session_infers_multi_page_sequence_from_write_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            (root / "C.md").write_text("# C\nold C\n", encoding="utf-8")
            (root / "D.md").write_text("# D\nold D\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            b_source = Path(tmpdir) / "B-new.md"
            c_source = Path(tmpdir) / "C-new.md"
            d_source = Path(tmpdir) / "D-new.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            c_source.write_text("# C\nnew C\n", encoding="utf-8")
            d_source.write_text("# D\nnew D\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args, actor="", session_id=""):
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
                        "--actor",
                        actor,
                        "--session-id",
                        session_id,
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
                actor="codex",
                session_id="work-1",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
                actor="codex",
                session_id="other-work",
            )
            c_update = run_json(
                "write-page",
                "C",
                "--from-file",
                str(c_source),
                "--output",
                str(root),
                "--no-journal",
                actor="codex",
                session_id="work-1",
            )
            d_update = run_json(
                "write-page",
                "D",
                "--from-file",
                str(d_source),
                "--output",
                str(root),
                "--no-journal",
            )
            plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "session",
                "--output",
                str(root),
            )
            no_session_plan = run_json(
                "revert-plan",
                d_update["event_id"],
                "--scope",
                "session",
                "--output",
                str(root),
            )
            a_text_after_plan = (root / "A.md").read_text(encoding="utf-8")
            b_text_after_plan = (root / "B.md").read_text(encoding="utf-8")
            c_text_after_plan = (root / "C.md").read_text(encoding="utf-8")
            d_text_after_plan = (root / "D.md").read_text(encoding="utf-8")
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows_after_plan = connection.execute(
                    """
                    SELECT event_id, event_type, actor, session_id
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(plan["scope"], "session")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertEqual(plan["session_id"], "work-1")
        self.assertEqual(plan["session_actor"], "codex")
        self.assertEqual(
            plan["session_event_ids"],
            [a_update["event_id"], c_update["event_id"]],
        )
        self.assertEqual(
            plan["candidate_event_ids"],
            [a_update["event_id"], c_update["event_id"]],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [c_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            [event["session_id"] for event in plan["candidate_events"]],
            ["work-1", "work-1"],
        )
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [c_update["event_id"], a_update["event_id"]],
        )
        self.assertEqual(
            plan["suggested_revert_events_args"],
            [
                "revert-events",
                a_update["event_id"],
                c_update["event_id"],
                "--output",
                str(root),
            ],
        )
        self.assertFalse(no_session_plan["complete"])
        self.assertFalse(no_session_plan["revertible"])
        self.assertIn("no session_id", no_session_plan["reason"])
        self.assertEqual(a_text_after_plan, "# A\nnew A\n")
        self.assertEqual(b_text_after_plan, "# B\nnew B\n")
        self.assertEqual(c_text_after_plan, "# C\nnew C\n")
        self.assertEqual(d_text_after_plan, "# D\nnew D\n")
        self.assertEqual(
            sqlite_event_rows_after_plan,
            [
                (a_update["event_id"], "page_update", "codex", "work-1"),
                (b_update["event_id"], "page_update", "codex", "other-work"),
                (c_update["event_id"], "page_update", "codex", "work-1"),
                (d_update["event_id"], "page_update", "", ""),
            ],
        )

    def test_revert_plan_explicit_scopes_include_required_same_page_dependents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nold B\n", encoding="utf-8")
            a_source = Path(tmpdir) / "A-new.md"
            b_source = Path(tmpdir) / "B-new.md"
            a_cleanup_source = Path(tmpdir) / "A-cleanup.md"
            a_source.write_text("# A\nnew A\n", encoding="utf-8")
            b_source.write_text("# B\nnew B\n", encoding="utf-8")
            a_cleanup_source.write_text("# A\nnew A\ncleanup\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            def run_json(*args, session_id=""):
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
                        "--actor",
                        "codex",
                        "--session-id",
                        session_id,
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

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
            a_update = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_source),
                "--output",
                str(root),
                "--no-journal",
                session_id="work-1",
            )
            b_update = run_json(
                "write-page",
                "B",
                "--from-file",
                str(b_source),
                "--output",
                str(root),
                "--no-journal",
                session_id="work-1",
            )
            a_cleanup = run_json(
                "write-page",
                "A",
                "--from-file",
                str(a_cleanup_source),
                "--output",
                str(root),
                "--no-journal",
                session_id="cleanup-work",
            )
            connection = sqlite3.connect(store_path)
            try:
                connection.executemany(
                    """
                    UPDATE events
                    SET created_at = ?
                    WHERE event_id = ?
                    """,
                    [
                        ("2026-06-27T00:00:00+00:00", a_update["event_id"]),
                        ("2026-06-27T00:01:00+00:00", b_update["event_id"]),
                        ("2026-06-27T00:10:00+00:00", a_cleanup["event_id"]),
                    ],
                )
                connection.commit()
            finally:
                connection.close()

            event_window_plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "event-window",
                "--after",
                "1",
                "--output",
                str(root),
            )
            time_burst_plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "time-burst",
                "--max-gap-seconds",
                "120",
                "--output",
                str(root),
            )
            session_plan = run_json(
                "revert-plan",
                a_update["event_id"],
                "--scope",
                "session",
                "--output",
                str(root),
            )
            projected_after_plan = {
                path.name: path.read_text(encoding="utf-8")
                for path in sorted(root.glob("*.md"))
            }

        for plan in (event_window_plan, time_burst_plan, session_plan):
            self.assertTrue(plan["complete"])
            self.assertTrue(plan["revertible"])
            self.assertEqual(plan["dependent_event_ids"], [a_cleanup["event_id"]])
            self.assertEqual(
                plan["candidate_event_ids"],
                [a_update["event_id"], b_update["event_id"], a_cleanup["event_id"]],
            )
            self.assertEqual(
                plan["revert_order_event_ids"],
                [a_cleanup["event_id"], b_update["event_id"], a_update["event_id"]],
            )
            self.assertEqual(
                [event["target_event_id"] for event in plan["reverted_events"]],
                [a_cleanup["event_id"], b_update["event_id"], a_update["event_id"]],
            )
            self.assertEqual(
                plan["suggested_revert_events_args"],
                [
                    "revert-events",
                    a_update["event_id"],
                    b_update["event_id"],
                    a_cleanup["event_id"],
                    "--output",
                    str(root),
                ],
            )
        self.assertEqual(event_window_plan["window_after"], 1)
        self.assertEqual(time_burst_plan["max_gap_seconds"], 120.0)
        self.assertEqual(session_plan["session_event_ids"], [a_update["event_id"], b_update["event_id"]])
        self.assertEqual(
            [event.get("session_id") for event in session_plan["candidate_events"]],
            ["work-1", "work-1", "cleanup-work"],
        )
        self.assertEqual(projected_after_plan["A.md"], "# A\nnew A\ncleanup\n")
        self.assertEqual(projected_after_plan["B.md"], "# B\nnew B\n")

    def test_write_event_metadata_defaults_from_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nold A\n", encoding="utf-8")
            source = Path(tmpdir) / "A-new.md"
            source.write_text("# A\nnew A\n", encoding="utf-8")
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
            env = {
                **os.environ,
                "GRASP_ACTOR": "env-codex",
                "GRASP_SESSION_ID": "env-session",
            }
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
                    "write-page",
                    "A",
                    "--from-file",
                    str(source),
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
            update = json.loads(completed.stdout)
            connection = sqlite3.connect(store_path)
            try:
                row = connection.execute(
                    """
                    SELECT event_id, actor, session_id
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(row, (update["event_id"], "env-codex", "env-session"))

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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            replay_text = (replay_root / "A.md").read_text(encoding="utf-8")

        peek_result = json.loads(peek_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        failed_error = json.loads(failed_completed.stderr)
        rollback_diagnostic = failed_error["diagnostic"]
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("store was reverted with event", failed_completed.stderr)
        self.assertEqual(rollback_diagnostic["type"], "projection_export_rollback")
        self.assertTrue(rollback_diagnostic["rolled_back"])
        self.assertEqual(rollback_diagnostic["target_event_id"], journal_events[1]["event_id"])
        self.assertEqual(rollback_diagnostic["target_event_type"], "section_append")
        self.assertEqual(rollback_diagnostic["target_event_project"], "wiki")
        self.assertEqual(rollback_diagnostic["rollback_event_id"], journal_events[-1]["event_id"])
        self.assertEqual(rollback_diagnostic["rollback_event_type"], "event_revert")
        self.assertEqual(rollback_diagnostic["rollback_event"], journal_events[-1])
        self.assertEqual(rollback_diagnostic["journal"], str(journal_path))
        self.assertTrue(rollback_diagnostic["journal_written"])
        self.assertEqual(rollback_diagnostic["original_error"]["type"], "IsADirectoryError")
        self.assertIn("projection export failed", rollback_diagnostic["reason"])
        self.assertEqual([event["event_type"] for event in journal_events], ["page_create", "section_append", "event_revert"])
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_create", "section_append", "event_revert"])
        self.assertEqual([row[0] for row in sqlite_event_rows], [event["event_id"] for event in journal_events])
        self.assertEqual([row[2] for row in sqlite_event_rows], ["wiki", "wiki", "wiki"])
        self.assertEqual(journal_events[-1]["payload"]["target_event_id"], journal_events[1]["event_id"])
        self.assertEqual(journal_events[-1]["payload"]["target_event_type"], "section_append")
        self.assertIn("projection export failed", journal_events[-1]["payload"]["reason"])
        sqlite_revert_payload = json.loads(sqlite_event_rows[-1][3])
        self.assertEqual(sqlite_revert_payload["target_event_id"], journal_events[1]["event_id"])
        self.assertEqual(sqlite_revert_payload["target_event_type"], "section_append")
        self.assertIn("projection export failed", sqlite_revert_payload["reason"])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(replay_text, "# A\n")
        self.assertEqual(replay_result["written_files"], ["A.md"])

    def test_projection_export_failure_no_journal_reports_rollback_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
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
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        failed_error = json.loads(failed_completed.stderr)
        rollback_diagnostic = failed_error["diagnostic"]
        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertEqual(rollback_diagnostic["type"], "projection_export_rollback")
        self.assertTrue(rollback_diagnostic["rolled_back"])
        self.assertEqual(rollback_diagnostic["target_event_type"], "section_append")
        self.assertEqual(rollback_diagnostic["target_event_project"], "wiki")
        self.assertEqual(rollback_diagnostic["rollback_event_type"], "event_revert")
        self.assertIsNone(rollback_diagnostic["journal"])
        self.assertFalse(rollback_diagnostic["journal_written"])
        self.assertEqual(rollback_diagnostic["original_error"]["type"], "IsADirectoryError")
        self.assertEqual([row[1] for row in sqlite_event_rows], ["section_append", "event_revert"])
        self.assertEqual(rollback_diagnostic["target_event_id"], sqlite_event_rows[0][0])
        self.assertEqual(rollback_diagnostic["rollback_event_id"], sqlite_event_rows[1][0])
        sqlite_revert_payload = json.loads(sqlite_event_rows[1][3])
        self.assertEqual(sqlite_revert_payload["target_event_id"], sqlite_event_rows[0][0])
        self.assertEqual(sqlite_revert_payload["target_event_type"], "section_append")
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])

    def test_write_command_refuses_unappendable_journal_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "blocked-events.jsonl"

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
            journal_path.mkdir()
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
                    "Should not write",
                    "--line",
                    "- blocked",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            page_text = (root / "A.md").read_text(encoding="utf-8")

        failed_error = json.loads(failed_completed.stderr)
        diagnostic = failed_error["diagnostic"]
        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertEqual(diagnostic["type"], "journal_append_preflight_failed")
        self.assertEqual(diagnostic["journal"], str(journal_path))
        self.assertFalse(diagnostic["store_mutated"])
        self.assertFalse(diagnostic["journal_written"])
        self.assertFalse(diagnostic["projection_written"])
        self.assertEqual(diagnostic["reason"], "journal path is a directory")
        self.assertEqual([row[0] for row in sqlite_event_rows], [])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(page_text, "# A\n")

    def test_revert_command_refuses_unappendable_journal_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "blocked-events.jsonl"

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
            append_completed = subprocess.run(
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
                    "Keep me",
                    "--line",
                    "- still here",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            append_result = json.loads(append_completed.stdout)
            journal_path.mkdir()
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
                    "revert-event",
                    append_result["event_id"],
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
                    "--line-limit",
                    "6",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            page_text = (root / "A.md").read_text(encoding="utf-8")

        failed_error = json.loads(failed_completed.stderr)
        diagnostic = failed_error["diagnostic"]
        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertEqual(diagnostic["type"], "journal_append_preflight_failed")
        self.assertEqual(diagnostic["journal"], str(journal_path))
        self.assertFalse(diagnostic["store_mutated"])
        self.assertFalse(diagnostic["journal_written"])
        self.assertFalse(diagnostic["projection_written"])
        self.assertEqual([row[0] for row in sqlite_event_rows], ["section_append"])
        self.assertEqual(
            [line["text"] for line in peek_result["lines"]],
            ["# A", "", "## Keep me", "- still here"],
        )
        self.assertEqual(page_text, "# A\n\n## Keep me\n- still here\n")

    def test_rename_projection_export_failure_preserves_previous_projection_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "Old.md").write_text("# Old\nbody\n", encoding="utf-8")
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
            (root / "New.md").mkdir()
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
                    "rename-page",
                    "Old",
                    "New",
                    "--new-path",
                    "New.md",
                    "--output",
                    str(root),
                    "--no-journal",
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
                    "Old",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            old_text = (
                (root / "Old.md").read_text(encoding="utf-8")
                if (root / "Old.md").exists()
                else None
            )
            new_is_dir = (root / "New.md").is_dir()

        failed_error = json.loads(failed_completed.stderr)
        rollback_diagnostic = failed_error["diagnostic"]
        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertEqual(rollback_diagnostic["type"], "projection_export_rollback")
        self.assertTrue(rollback_diagnostic["rolled_back"])
        self.assertEqual(rollback_diagnostic["target_event_type"], "page_rename")
        self.assertEqual(rollback_diagnostic["rollback_event_type"], "event_revert")
        self.assertEqual(rollback_diagnostic["original_error"]["type"], "IsADirectoryError")
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_rename", "event_revert"])
        self.assertEqual(rollback_diagnostic["target_event_id"], sqlite_event_rows[0][0])
        self.assertEqual(rollback_diagnostic["rollback_event_id"], sqlite_event_rows[1][0])
        sqlite_revert_payload = json.loads(sqlite_event_rows[1][2])
        self.assertEqual(sqlite_revert_payload["target_event_id"], sqlite_event_rows[0][0])
        self.assertEqual(sqlite_revert_payload["target_event_type"], "page_rename")
        self.assertEqual(peek_result["page"]["title"], "Old")
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# Old", "body"])
        self.assertEqual(old_text, "# Old\nbody\n")
        self.assertTrue(new_is_dir)

    def test_write_page_refuses_export_when_other_projection_file_is_dirty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            (root / "B.md").write_text("# B\n- local draft\n", encoding="utf-8")
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
                    "write-page",
                    "A",
                    "--line",
                    "# A",
                    "--line",
                    "- replacement",
                    "--output",
                    str(root),
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            b_text = (root / "B.md").read_text(encoding="utf-8")

        failed_error = json.loads(failed_completed.stderr)
        rollback_diagnostic = failed_error["diagnostic"]
        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertEqual(rollback_diagnostic["type"], "projection_export_rollback")
        self.assertTrue(rollback_diagnostic["rolled_back"])
        self.assertEqual(rollback_diagnostic["target_event_type"], "page_update")
        self.assertEqual(rollback_diagnostic["rollback_event_type"], "event_revert")
        self.assertEqual(rollback_diagnostic["original_error"]["type"], "ValueError")
        self.assertIn("dirty paths outside the current write target", rollback_diagnostic["original_error"]["message"])
        self.assertIn("B.md", rollback_diagnostic["original_error"]["message"])
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_update", "event_revert"])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(a_text, "# A\n")
        self.assertEqual(b_text, "# B\n- local draft\n")

    def test_write_page_projection_export_failure_does_not_partially_update_prior_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
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
            (root / "B.md").unlink()
            (root / "B.md").mkdir()
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
                    "write-page",
                    "A",
                    "--line",
                    "# A",
                    "--line",
                    "- replacement",
                    "--output",
                    str(root),
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            b_is_dir = (root / "B.md").is_dir()

        failed_error = json.loads(failed_completed.stderr)
        rollback_diagnostic = failed_error["diagnostic"]
        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertEqual(rollback_diagnostic["type"], "projection_export_rollback")
        self.assertTrue(rollback_diagnostic["rolled_back"])
        self.assertEqual(rollback_diagnostic["target_event_type"], "page_update")
        self.assertEqual(rollback_diagnostic["rollback_event_type"], "event_revert")
        self.assertEqual(rollback_diagnostic["original_error"]["type"], "IsADirectoryError")
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_update", "event_revert"])
        self.assertEqual(rollback_diagnostic["target_event_id"], sqlite_event_rows[0][0])
        self.assertEqual(rollback_diagnostic["rollback_event_id"], sqlite_event_rows[1][0])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(a_text, "# A\n")
        self.assertTrue(b_is_dir)

    def test_write_page_allows_dirty_projection_file_when_it_is_the_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            (root / "A.md").write_text("# A\n- local draft\n", encoding="utf-8")
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
                    "write-page",
                    "A",
                    "--from-file",
                    str(root / "A.md"),
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            b_text = (root / "B.md").read_text(encoding="utf-8")

        result = json.loads(completed.stdout)
        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(result["source_path"], "A.md")
        self.assertEqual(result["projection"]["written_files"], [])
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_update"])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A", "- local draft"])
        self.assertEqual(a_text, "# A\n- local draft\n")
        self.assertEqual(b_text, "# B\n")

    def test_write_page_line_refuses_dirty_target_projection_file_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            (root / "A.md").write_text("# A\n- local draft\n", encoding="utf-8")
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
                    "write-page",
                    "A",
                    "--line",
                    "# A",
                    "--line",
                    "- replacement",
                    "--output",
                    str(root),
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")

        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty write target paths", failed_completed.stderr)
        self.assertIn("A.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, [])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(a_text, "# A\n- local draft\n")

    def test_append_section_refuses_dirty_target_projection_file_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            (root / "A.md").write_text("# A\n- local draft\n", encoding="utf-8")
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
                    "Notes",
                    "--line",
                    "- appended",
                    "--output",
                    str(root),
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")

        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty write target paths", failed_completed.stderr)
        self.assertIn("A.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, [])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(a_text, "# A\n- local draft\n")

    def test_append_log_refuses_dirty_target_projection_file_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "Log.md").write_text("# Log\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            (root / "Log.md").write_text("# Log\n- local draft\n", encoding="utf-8")
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
                    "append-log",
                    "--timestamp",
                    "2026-06-28 06:45",
                    "--op",
                    "test",
                    "--summary",
                    "blocked",
                    "--line",
                    "- appended",
                    "--output",
                    str(root),
                    "--no-journal",
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
                    "Log",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            log_text = (root / "Log.md").read_text(encoding="utf-8")

        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty write target paths", failed_completed.stderr)
        self.assertIn("Log.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, [])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# Log"])
        self.assertEqual(log_text, "# Log\n- local draft\n")

    def test_rename_page_refuses_dirty_target_projection_file_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            (root / "A.md").write_text("# A\n- local draft\n", encoding="utf-8")
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
                    "rename-page",
                    "A",
                    "Renamed",
                    "--new-path",
                    "Renamed.md",
                    "--output",
                    str(root),
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            renamed_exists = (root / "Renamed.md").exists()

        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty write target paths", failed_completed.stderr)
        self.assertIn("A.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, [])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A"])
        self.assertEqual(a_text, "# A\n- local draft\n")
        self.assertFalse(renamed_exists)

    def test_write_page_allows_other_dirty_projection_file_when_it_matches_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            subprocess.run(
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
                    "- first stored change",
                    "--output",
                    str(root),
                    "--no-journal",
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
                    "write-page",
                    "B",
                    "--line",
                    "# B",
                    "--line",
                    "- second stored change",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            b_text = (root / "B.md").read_text(encoding="utf-8")

        result = json.loads(completed.stdout)
        self.assertEqual(result["source_path"], "B.md")
        self.assertEqual(result["projection"]["written_files"], ["B.md"])
        self.assertEqual(sqlite_event_types, ["page_update", "page_update"])
        self.assertEqual(a_text, "# A\n- first stored change\n")
        self.assertEqual(b_text, "# B\n- second stored change\n")

    def test_revert_event_refuses_dirty_projection_file_outside_target_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            update_completed = subprocess.run(
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
                    "- stored change",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            update_result = json.loads(update_completed.stdout)
            (root / "B.md").write_text("# B\n- local draft\n", encoding="utf-8")
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
                    "revert-event",
                    update_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            b_text = (root / "B.md").read_text(encoding="utf-8")

        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty paths outside the current write target", failed_completed.stderr)
        self.assertIn("B.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, ["page_update"])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A", "- stored change"])
        self.assertEqual(a_text, "# A\n- stored change\n")
        self.assertEqual(b_text, "# B\n- local draft\n")

    def test_revert_target_projection_source_paths_falls_back_to_manifest_page_id(self):
        from grasp.cli import revert_target_projection_source_paths
        from grasp.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
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
            connection = sqlite3.connect(store_path)
            try:
                page_id = connection.execute(
                    "SELECT id FROM pages WHERE project = ? AND title = ?",
                    ("wiki", "A"),
                ).fetchone()[0]
            finally:
                connection.close()

            store = SQLiteStore(store_path, project="wiki")
            try:
                paths = revert_target_projection_source_paths(
                    store,
                    {"event_type": "page_update", "payload": {"page_id": page_id}},
                )
            finally:
                store.close()

        self.assertEqual(paths, {"A.md"})

    def test_revert_event_refuses_dirty_target_projection_file_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            update_result = json.loads(subprocess.run(
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
                    "- stored change",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout)
            (root / "A.md").write_text("# A\n- local draft\n", encoding="utf-8")
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
                    "revert-event",
                    update_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")

        peek_result = json.loads(peek_completed.stdout)
        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty reverted target paths", failed_completed.stderr)
        self.assertIn("A.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, ["page_update"])
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# A", "- stored change"])
        self.assertEqual(a_text, "# A\n- local draft\n")

    def test_revert_events_refuses_dirty_projection_file_outside_targets_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            (root / "C.md").write_text("# C\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            a_update = json.loads(subprocess.run(
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
                    "- new A",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout)
            c_update = json.loads(subprocess.run(
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
                    "C",
                    "--line",
                    "# C",
                    "--line",
                    "- new C",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout)
            (root / "B.md").write_text("# B\n- local draft\n", encoding="utf-8")
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
                    "revert-events",
                    a_update["event_id"],
                    c_update["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            b_text = (root / "B.md").read_text(encoding="utf-8")
            c_text = (root / "C.md").read_text(encoding="utf-8")

        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty paths outside the current write target", failed_completed.stderr)
        self.assertIn("B.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, ["page_update", "page_update"])
        self.assertEqual(a_text, "# A\n- new A\n")
        self.assertEqual(b_text, "# B\n- local draft\n")
        self.assertEqual(c_text, "# C\n- new C\n")

    def test_revert_event_include_dependents_refuses_dirty_projection_file_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            root = repo_root / "wiki"
            root.mkdir(parents=True)
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            init_git_repo(repo_root)
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
            first_result = json.loads(subprocess.run(
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
                    "First",
                    "--line",
                    "- first",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout)
            subprocess.run(
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
                    "Second",
                    "--line",
                    "- second",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            (root / "B.md").write_text("# B\n- local draft\n", encoding="utf-8")
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
                    "revert-event",
                    first_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
                    "--include-dependents",
                ],
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_types = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT event_type
                        FROM events
                        ORDER BY event_sequence
                        """
                    ).fetchall()
                ]
            finally:
                connection.close()
            a_text = (root / "A.md").read_text(encoding="utf-8")
            b_text = (root / "B.md").read_text(encoding="utf-8")

        self.assertEqual(failed_completed.returncode, 2)
        self.assertIn("dirty paths outside the current write target", failed_completed.stderr)
        self.assertIn("B.md", failed_completed.stderr)
        self.assertEqual(sqlite_event_types, ["section_append", "section_append"])
        self.assertIn("- first", a_text)
        self.assertIn("- second", a_text)
        self.assertEqual(b_text, "# B\n- local draft\n")

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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()

        section_result = json.loads(section_completed.stdout)
        status_result = json.loads(status_completed.stdout)
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
        self.assertEqual(
            [row[1] for row in sqlite_event_rows],
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
        self.assertEqual([row[2] for row in sqlite_event_rows], ["wiki"] * 7)
        self.assertEqual(sqlite_event_rows[2][0], section_result["event_id"])
        self.assertEqual(sqlite_event_rows[3][0], log_result["event_id"])
        self.assertEqual(sqlite_event_rows[4][0], revert_result["event_id"])
        self.assertEqual(sqlite_event_rows[5][0], write_result["event_id"])
        self.assertEqual(sqlite_event_rows[6][0], revert_write_result["event_id"])
        self.assertEqual(json.loads(sqlite_event_rows[2][3])["heading"], "Updates")
        self.assertEqual(json.loads(sqlite_event_rows[2][3])["source_path"], "A.md")
        self.assertEqual(json.loads(sqlite_event_rows[3][3])["op"], "test")
        self.assertEqual(json.loads(sqlite_event_rows[3][3])["source_path"], "Log.md")
        self.assertEqual(json.loads(sqlite_event_rows[4][3])["target_event_id"], log_result["event_id"])
        self.assertEqual(json.loads(sqlite_event_rows[6][3])["target_event_id"], write_result["event_id"])
        self.assertIn("\n## Updates\n- detail [[B]]\n", page_text)
        self.assertNotIn("- rewritten [[C]]", page_text)
        self.assertEqual(log_text, "# Log\n")
        self.assertEqual(section_result["source_path"], "A.md")
        self.assertEqual(log_result["source_path"], "Log.md")
        self.assertEqual(section_result["edge_count"], 1)
        self.assertEqual(section_result["projection"]["written_files"], ["A.md"])
        self.assertEqual(log_result["projection"]["written_files"], ["Log.md"])
        self.assertEqual(write_result["source_path"], "A.md")
        self.assertEqual(write_result["edge_count"], 1)
        self.assertEqual(write_result["projection"]["written_files"], ["A.md"])
        self.assertEqual(status_result["journal_event_count"], 4)
        self.assertEqual(status_result["journal_project_event_count"], 4)
        self.assertEqual(status_result["sqlite_event_count"], 4)
        self.assertTrue(status_result["event_streams_match"])
        self.assertIsNone(status_result["event_stream_mismatch"])
        self.assertTrue(status_result["projection"]["ok"])
        self.assertTrue(status_result["strict_ok"])
        self.assertEqual(status_result["strict_failures"], [])
        self.assertFalse(status_result["journal_log_stale"])
        self.assertEqual(status_result["journal_log_changed_files"], [])
        self.assertTrue(status_result["journal_log_projection"]["ok"])
        self.assertEqual(status_result["journal_log_projection"]["regenerated_files"], ["Log.md"])
        self.assertEqual(revert_result["target_event_type"], "log_append")
        self.assertEqual(revert_result["projection"]["written_files"], ["Log.md"])
        self.assertEqual(revert_result["removed_line_count"], 3)
        self.assertEqual(revert_write_result["target_event_type"], "page_update")
        self.assertEqual(revert_write_result["restored_line_count"], 4)
        self.assertTrue(replay_result["ok"])
        self.assertEqual(replay_result["file_count"], 2)

    def test_no_journal_writes_update_store_and_projection_only(self):
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
            original_journal_text = journal_path.read_text(encoding="utf-8")
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
                    "--no-journal",
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
                    "no journal",
                    "--line",
                    "- log detail",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            log_result = json.loads(log_completed.stdout)
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
                    "--no-journal",
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
                    "--no-journal",
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
                    "A",
                    "Renamed A",
                    "--new-path",
                    "Renamed.md",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            rename_result = json.loads(rename_completed.stdout)
            revert_rename_completed = subprocess.run(
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
                    "--no-journal",
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
                    "--no-journal",
                    "--strict",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            export_completed = subprocess.run(
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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_type, project
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            journal_text_after_writes = journal_path.read_text(encoding="utf-8")
            page_text = (root / "A.md").read_text(encoding="utf-8")
            log_text = (root / "Log.md").read_text(encoding="utf-8")
            renamed_exists_after_revert = (root / "Renamed.md").exists()

        section_result = json.loads(section_completed.stdout)
        write_result = json.loads(write_completed.stdout)
        revert_result = json.loads(revert_completed.stdout)
        revert_rename_result = json.loads(revert_rename_completed.stdout)
        status_result = json.loads(status_completed.stdout)
        export_result = json.loads(export_completed.stdout)
        self.assertIsNone(section_result["journal"])
        self.assertFalse(section_result["journal_written"])
        self.assertIsNone(log_result["journal"])
        self.assertFalse(log_result["journal_written"])
        self.assertIsNone(write_result["journal"])
        self.assertFalse(write_result["journal_written"])
        self.assertIsNone(revert_result["journal"])
        self.assertFalse(revert_result["journal_written"])
        self.assertIsNone(rename_result["journal"])
        self.assertFalse(rename_result["journal_written"])
        self.assertIsNone(revert_rename_result["journal"])
        self.assertFalse(revert_rename_result["journal_written"])
        self.assertEqual(journal_text_after_writes, original_journal_text)
        self.assertEqual(
            [row[0] for row in sqlite_event_rows],
            [
                "page_create",
                "page_create",
                "section_append",
                "log_append",
                "page_update",
                "event_revert",
                "page_rename",
                "event_revert",
            ],
        )
        self.assertEqual([row[1] for row in sqlite_event_rows], ["wiki"] * 8)
        self.assertTrue(status_result["strict_ok"])
        self.assertEqual(status_result["strict_failures"], [])
        self.assertFalse(status_result["journal_required"])
        self.assertFalse(status_result["journal_exists"])
        self.assertTrue(status_result["event_streams_match"])
        self.assertEqual(status_result["sqlite_event_count"], 8)
        self.assertTrue(status_result["projection"]["ok"])
        self.assertFalse(status_result["semantic_log_stale"])
        self.assertEqual(status_result["semantic_log_changed_files"], [])
        self.assertTrue(status_result["semantic_log_projection"]["ok"])
        self.assertEqual(status_result["semantic_log_projection"]["log_event_source"], "sqlite")
        self.assertEqual(
            status_result["semantic_log_projection"]["projection_policy"]["generated_overlays"],
            ["sqlite-events-log"],
        )
        self.assertTrue(export_result["ok"])
        self.assertEqual(page_text, "# A\n- rewritten [[C]]\n")
        self.assertEqual(log_text, "# Log\n")
        self.assertFalse(renamed_exists_after_revert)

    def test_write_status_no_journal_strict_fails_on_sqlite_semantic_log_drift(self):
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
                    "sqlite entry",
                    "--line",
                    "- sqlite line",
                    "--output",
                    str(root),
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            (root / "Log.md").write_text(
                "# Log\n\n## [2026-06-26 02:00] test | manual replacement\n- not from sqlite events\n",
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
                    "--no-journal",
                    "--strict",
                ],
                text=True,
                capture_output=True,
            )

        status_result = json.loads(status_completed.stdout)
        self.assertEqual(status_completed.returncode, 1)
        self.assertTrue(status_result["projection"]["ok"])
        self.assertFalse(status_result["strict_ok"])
        self.assertEqual([failure["type"] for failure in status_result["strict_failures"]], ["semantic_log_stale"])
        self.assertTrue(status_result["semantic_log_stale"])
        self.assertEqual(status_result["semantic_log_changed_files"], ["Log.md"])
        self.assertFalse(status_result["semantic_log_projection"]["ok"])
        self.assertEqual(status_result["semantic_log_projection"]["changed_files"], ["Log.md"])
        self.assertEqual(status_result["semantic_log_projection"]["log_event_source"], "sqlite")
        self.assertEqual(
            status_result["semantic_log_projection"]["projection_policy"]["generated_overlays"],
            ["sqlite-events-log"],
        )

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
        self.assertIn("journal_log_stale", [failure["type"] for failure in status_result["strict_failures"]])
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
        self.assertIsNone(status_result["semantic_log_projection"])
        self.assertIsNone(status_result["semantic_log_error"])

    def test_write_status_strict_fails_when_event_streams_diverge(self):
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
            journal_path.write_text("", encoding="utf-8")
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
        self.assertTrue(status_result["journal_exists"])
        self.assertEqual(status_result["journal_event_count"], 0)
        self.assertEqual(status_result["journal_project_event_count"], 0)
        self.assertEqual(status_result["sqlite_event_count"], 1)
        self.assertFalse(status_result["event_streams_match"])
        self.assertEqual(status_result["event_stream_mismatch"]["kind"], "count_mismatch")
        self.assertEqual(status_result["event_stream_mismatch"]["sqlite_event"]["event_type"], "page_create")
        self.assertEqual([failure["type"] for failure in status_result["strict_failures"]], ["event_stream_mismatch"])

    def test_write_status_accepts_legacy_journal_records_around_sqlite_events(self):
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
            legacy_prefix = {
                "schema_version": 1,
                "event_id": "legacy-prefix",
                "event_type": "projection_export",
                "project": "wiki",
                "created_at": "2026-06-26T00:00:00+00:00",
                "payload": {},
            }
            legacy_middle = {
                "schema_version": 1,
                "event_id": "legacy-middle",
                "event_type": "projection_export",
                "project": "wiki",
                "created_at": "2026-06-26T00:01:00+00:00",
                "payload": {},
            }
            legacy_tail = {
                "schema_version": 1,
                "event_id": "legacy-tail",
                "event_type": "projection_export",
                "project": "wiki",
                "created_at": "2026-06-26T00:02:00+00:00",
                "payload": {},
            }
            original_journal_lines = journal_path.read_text(encoding="utf-8").splitlines()
            journal_path.write_text(
                "\n".join(
                    [
                        json.dumps(legacy_prefix, ensure_ascii=False, sort_keys=True),
                        original_journal_lines[0],
                        json.dumps(legacy_middle, ensure_ascii=False, sort_keys=True),
                        *original_journal_lines[1:],
                        json.dumps(legacy_tail, ensure_ascii=False, sort_keys=True),
                    ]
                )
                + "\n",
                encoding="utf-8",
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

        status_result = json.loads(status_completed.stdout)
        self.assertEqual(status_result["journal_project_event_count"], 5)
        self.assertEqual(status_result["sqlite_event_count"], 2)
        self.assertTrue(status_result["event_streams_match"])
        self.assertIsNone(status_result["event_stream_mismatch"])
        self.assertTrue(status_result["strict_ok"])
        self.assertEqual(status_result["strict_failures"], [])

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
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_id, event_type, project, payload_json
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
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
        self.assertEqual([row[1] for row in sqlite_event_rows], ["page_create", "page_create", "page_rename", "event_revert"])
        self.assertEqual(sqlite_event_rows[2][0], rename_result["event_id"])
        self.assertEqual(sqlite_event_rows[2][2], "wiki")
        sqlite_rename_payload = json.loads(sqlite_event_rows[2][3])
        self.assertEqual(sqlite_rename_payload["previous_title"], "Old")
        self.assertEqual(sqlite_rename_payload["title"], "New")
        self.assertEqual(sqlite_rename_payload["previous_source_path"], "Old.md")
        self.assertEqual(sqlite_rename_payload["source_path"], "New.md")
        self.assertEqual(sqlite_event_rows[3][0], revert_result["event_id"])
        sqlite_revert_payload = json.loads(sqlite_event_rows[3][3])
        self.assertEqual(sqlite_revert_payload["target_event_id"], rename_result["event_id"])
        self.assertEqual(sqlite_revert_payload["target_event_type"], "page_rename")
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
        self.assertEqual(revert_result["target_event_source"], "sqlite")
        self.assertEqual(revert_result["restored_line_count"], 2)
        self.assertTrue(old_exists_after_revert)
        self.assertFalse(new_exists_after_revert)
        self.assertTrue(replay_after_revert["ok"])

    def test_revert_rename_export_failure_preserves_current_projection_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "Old.md").write_text("# Old\nbody\n", encoding="utf-8")
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
                    "--no-journal",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            rename_result = json.loads(rename_completed.stdout)
            new_text_before_revert = (root / "New.md").read_text(encoding="utf-8")
            (root / "Old.md").mkdir()
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
                    "revert-event",
                    rename_result["event_id"],
                    "--output",
                    str(root),
                    "--no-journal",
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
                    "Old",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            connection = sqlite3.connect(store_path)
            try:
                sqlite_event_rows = connection.execute(
                    """
                    SELECT event_type
                    FROM events
                    ORDER BY event_sequence
                    """
                ).fetchall()
            finally:
                connection.close()
            new_text_after_failure = (
                (root / "New.md").read_text(encoding="utf-8")
                if (root / "New.md").exists()
                else None
            )
            old_is_dir = (root / "Old.md").is_dir()

        peek_result = json.loads(peek_completed.stdout)
        failed_error = json.loads(failed_completed.stderr)
        diagnostic = failed_error["diagnostic"]
        self.assertEqual(failed_completed.returncode, 2)
        self.assertEqual(diagnostic["type"], "revert_projection_export_failed")
        self.assertEqual(diagnostic["phase"], "export_reverted_projection")
        self.assertTrue(diagnostic["store_reverted"])
        self.assertEqual(diagnostic["target_event_source"], "sqlite")
        self.assertEqual(diagnostic["target_event_ids"], [rename_result["event_id"]])
        self.assertEqual(diagnostic["target_event_types"], ["page_rename"])
        self.assertEqual(diagnostic["revert_event_count"], 1)
        self.assertEqual(diagnostic["revert_event_types"], ["event_revert"])
        self.assertEqual(diagnostic["pending_removed_files"], ["New.md"])
        self.assertFalse(diagnostic["journal_written"])
        self.assertEqual(diagnostic["original_error"]["type"], "IsADirectoryError")
        self.assertEqual(diagnostic["output"], str(root))
        self.assertEqual([row[0] for row in sqlite_event_rows], ["page_rename", "event_revert"])
        self.assertEqual(peek_result["page"]["title"], "Old")
        self.assertEqual([line["text"] for line in peek_result["lines"]], ["# Old", "body"])
        self.assertEqual(new_text_after_failure, new_text_before_revert)
        self.assertTrue(old_is_dir)

    def test_write_page_create_then_rename_preserves_old_alias_after_fresh_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nlink [[Draft title]]\n", encoding="utf-8")
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
            subprocess.run(
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
                    "Draft title",
                    "--create",
                    "--path",
                    "note.md",
                    "--line",
                    "# Draft title",
                    "--line",
                    "body",
                    "--output",
                    str(root),
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
                    "Draft title",
                    "Final title",
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            renamed_text = (root / "note.md").read_text(encoding="utf-8")
            reimport_store_path = Path(tmpdir) / "reimport.sqlite"
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
                    "Draft title",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        rename_result = json.loads(rename_completed.stdout)
        reimport_read_old = json.loads(reimport_read_old_completed.stdout)
        self.assertEqual(rename_result["previous_aliases"], ["note"])
        self.assertEqual(rename_result["aliases"], ["note", "Draft title"])
        self.assertEqual(
            renamed_text,
            "\n".join(
                [
                    "---",
                    f"id: {rename_result['page']['id']}",
                    "title: Final title",
                    "aliases:",
                    "  - Draft title",
                    "---",
                    "# Final title",
                    "body",
                    "",
                ]
            ),
        )
        self.assertEqual(reimport_read_old["page"]["id"], rename_result["page"]["id"])
        self.assertEqual(reimport_read_old["page"]["title"], "Final title")
        self.assertEqual(reimport_read_old["backlink_count_total"], 1)

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
