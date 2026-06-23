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
    "link-stats",
    "peek",
    "suggest",
    "search",
    "export-ai",
    "sync",
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
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["page"]["title"], "A")
        self.assertEqual(result["lines"][0]["text"], "A")

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
