import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from grasp.cli import format_import_forest
from grasp.forest import import_forest_from_registry, parse_wiki_registry
from grasp.sqlite_store import SQLiteStore


class ForestImportTests(unittest.TestCase):
    def test_parse_wiki_registry_reads_name_and_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            registry = root / "wikis.yaml"
            registry.write_text(
                "\n".join(
                    [
                        "# comment",
                        "wikis:",
                        "  - name: alpha",
                        "    path: ./alpha",
                        "    purpose: alpha # comment",
                        "  - name: 'beta'",
                        "    path: \"./beta\"",
                    ]
                ),
                encoding="utf-8",
            )

            entries = parse_wiki_registry(registry)

            self.assertEqual(entries[0]["name"], "alpha")
            self.assertEqual(entries[0]["path"], "./alpha")
            self.assertEqual(entries[1]["name"], "beta")
            self.assertEqual(entries[1]["path"], "./beta")

    def test_import_forest_imports_projects_and_reports_ambiguities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            registry = root / "wikis.yaml"
            store_path = root / "forest.sqlite"
            for name in ("one", "two"):
                wiki = root / name / "wiki"
                wiki.mkdir(parents=True)
                (wiki / "A.md").write_text(
                    "\n".join(["---", "aliases: [Shared]", "---", f"# {name} A"]),
                    encoding="utf-8",
                )
                (wiki / "B.md").write_text(
                    "\n".join(["---", "aliases: [Shared]", "---", f"# {name} B"]),
                    encoding="utf-8",
                )
                (wiki / "Source.md").write_text("links to [[Shared]]\n", encoding="utf-8")
            registry.write_text(
                "\n".join(
                    [
                        "wikis:",
                        f"  - name: one\n    path: {root / 'one'}",
                        f"  - name: two\n    path: {root / 'two'}",
                        f"  - name: missing\n    path: {root / 'missing'}",
                    ]
                ),
                encoding="utf-8",
            )

            result = import_forest_from_registry(
                registry,
                store_path,
                exclude_dirs=("raw",),
                ambiguity_limit=10,
                ambiguity_candidate_limit=1,
            )

            self.assertEqual(result["entry_count"], 3)
            self.assertEqual(result["success_count"], 2)
            self.assertEqual(result["missing_count"], 1)
            self.assertEqual(result["failure_count"], 0)
            self.assertEqual(result["aggregate"]["projects"], 2)
            self.assertEqual(result["aggregate"]["pages"], 6)
            self.assertEqual(result["aggregate"]["edges"], 2)
            self.assertEqual(result["ambiguities"]["handle_count"], 2)
            self.assertEqual(result["ambiguities"]["project_count"], 2)
            self.assertEqual(
                {project["project"]: project["ambiguous_link_count"] for project in result["ambiguities"]["projects"]},
                {"one": 1, "two": 1},
            )
            self.assertEqual(
                {project["name"]: project["status"] for project in result["projects"]},
                {"one": "success", "two": "success", "missing": "missing"},
            )
            text = format_import_forest(result)
            self.assertIn("# Import Forest", text)
            self.assertIn("success: 2", text)
            self.assertIn("missing: 1", text)
            self.assertIn("ambiguities: 2 / 2 handles returned", text)

    def test_cli_import_forest_creates_store_from_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "one" / "wiki"
            wiki.mkdir(parents=True)
            (wiki / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (wiki / "B.md").write_text("# B\n", encoding="utf-8")
            registry = root / "wikis.yaml"
            registry.write_text(f"wikis:\n  - name: one\n    path: {root / 'one'}\n", encoding="utf-8")
            store_path = root / "forest.sqlite"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "import-forest",
                    str(registry),
                    "--markdown-exclude-dir",
                    "raw",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            result = json.loads(completed.stdout)
            self.assertEqual(result["entry_count"], 1)
            self.assertEqual(result["success_count"], 1)
            self.assertEqual(result["failure_count"], 0)
            self.assertEqual(result["aggregate"]["projects"], 1)
            self.assertEqual(result["aggregate"]["pages"], 2)
            self.assertTrue(store_path.exists())

    def test_import_forest_refreshes_whole_store_derivatives_after_all_projects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            one = root / "one" / "wiki"
            two = root / "two" / "wiki"
            one.mkdir(parents=True)
            two.mkdir(parents=True)
            (one / "Source.md").write_text("# Source\nlinks to [[BetaOnly]]\n", encoding="utf-8")
            (two / "BetaOnly.md").write_text("# BetaOnly\n", encoding="utf-8")
            registry = root / "wikis.yaml"
            registry.write_text(
                "\n".join(
                    [
                        "wikis:",
                        f"  - name: one\n    path: {root / 'one'}",
                        f"  - name: two\n    path: {root / 'two'}",
                    ]
                ),
                encoding="utf-8",
            )
            store_path = root / "forest.sqlite"

            result = import_forest_from_registry(registry, store_path)

            self.assertEqual(result["aggregate"]["projects"], 2)
            self.assertEqual(result["aggregate"]["pages"], 2)
            self.assertEqual(result["aggregate"]["edges"], 2)
            store = SQLiteStore(store_path)
            try:
                path = store.paths_between("Source", "BetaOnly", max_depth=1, limit=1)
                self.assertEqual(path["path_count"], 1)
                self.assertEqual(path["paths"][0]["edges"][0]["connection_strength"], "weak")
                self.assertEqual(path["paths"][0]["edges"][0]["link_kind"], "inferred-normalized-title")
                self.assertEqual(path["paths"][0]["edges"][0]["target_project"], "two")
            finally:
                store.close()

    def test_import_forest_reports_duplicate_registry_names_without_replacing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            registry = root / "wikis.yaml"
            store_path = root / "forest.sqlite"
            for folder, title in (("first", "First"), ("second", "Second")):
                wiki = root / folder / "wiki"
                wiki.mkdir(parents=True)
                (wiki / f"{title}.md").write_text(f"# {title}\n", encoding="utf-8")
            registry.write_text(
                "\n".join(
                    [
                        "wikis:",
                        f"  - name: duplicated\n    path: {root / 'first'}",
                        f"  - name: duplicated\n    path: {root / 'second'}",
                    ]
                ),
                encoding="utf-8",
            )

            result = import_forest_from_registry(registry, store_path)

            self.assertEqual(result["success_count"], 1)
            self.assertEqual(result["failure_count"], 1)
            self.assertEqual(result["aggregate"]["projects"], 1)
            self.assertEqual(result["projects"][1]["diagnostic"]["type"], "registry_project_duplicate")


if __name__ == "__main__":
    unittest.main()
