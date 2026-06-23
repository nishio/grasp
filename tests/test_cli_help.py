import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


COMMANDS = [
    "import",
    "stats",
    "read",
    "backlinks",
    "related",
    "path",
    "link-stats",
    "peek",
    "suggest",
    "search",
    "export-ai",
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
        unresolved_help = run_grasp_help("unresolved")
        self.assertIn("--cosense", import_help)
        self.assertNotIn("--force", import_help)
        self.assertIn("--unresolved-limit", read_help)
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
            with sqlite3.connect(store_path) as connection:
                connection.execute(
                    "UPDATE metadata SET value = '3' WHERE key = 'schema_version'"
                )

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

        result = json.loads(completed.stdout)
        self.assertEqual(result["page"]["title"], "A")
        self.assertEqual(result["lines"][0]["text"], "A")
        self.assertEqual(result["related"][0]["title"], "C")
        self.assertEqual(result["related"][0]["snippet_lines"][0]["text"], "C")
        self.assertTrue(result["related"][0]["snippet_truncated"])

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

    def test_importing_folder_reports_markdown_import_is_not_implemented(self):
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
        self.assertIn("Markdown/Obsidian folder import is not implemented yet", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
