import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_VAULT = ROOT / "examples" / "persona2a-vault"


def run_grasp_json(*args):
    completed = subprocess.run(
        [sys.executable, "-m", "grasp", *map(str, args)],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


class Persona2aDemoTests(unittest.TestCase):
    def test_bundled_dense_markdown_vault_demo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            vault = tmp / "vault"
            store = tmp / "persona2a.sqlite"
            project = "persona2a"
            shutil.copytree(DEMO_VAULT, vault)

            imported = run_grasp_json(
                "--store",
                store,
                "--json",
                "import",
                "--markdown",
                vault,
                "--project",
                project,
            )
            self.assertEqual(imported["project"], project)
            self.assertGreaterEqual(imported["pages"], 8)

            read_result = run_grasp_json(
                "--store",
                store,
                "--project",
                project,
                "--json",
                "read",
                "Ingestion Pipeline",
                "--line-limit",
                "20",
                "--backlinks-limit",
                "5",
                "--related-limit",
                "5",
                "--unresolved-limit",
                "5",
            )
            self.assertEqual(read_result["page"]["title"], "Ingestion Pipeline")
            unresolved_titles = {item["title"] for item in read_result["unresolved_targets"]}
            self.assertIn("Frontmatter Normalizer", unresolved_titles)

            backlinks = run_grasp_json(
                "--store",
                store,
                "--project",
                project,
                "--json",
                "backlinks",
                "Context Budget",
                "--limit",
                "10",
            )
            backlink_sources = {item["source_title"] for item in backlinks["backlinks"]}
            self.assertIn("Ingestion Pipeline", backlink_sources)
            self.assertIn("Agent Memory", backlink_sources)

            search = run_grasp_json(
                "--store",
                store,
                "--project",
                project,
                "--json",
                "search",
                "stale write",
                "--context",
                "1",
                "--limit",
                "5",
            )
            self.assertGreaterEqual(search["count_returned"], 1)

            append = run_grasp_json(
                "--store",
                store,
                "--project",
                project,
                "--actor",
                "demo",
                "--session-id",
                "persona2a-demo-test",
                "--json",
                "append-log",
                "--op",
                "demo",
                "--summary",
                "capture retrieval answer",
                "--line",
                "- Answer cites [[Ingestion Pipeline]], [[Context Budget]], and [[Stale Write Guard]].",
                "--output",
                vault,
                "--no-journal",
            )
            self.assertTrue(append["event_id"])
            self.assertEqual(append["source_path"], "Log.md")
            self.assertEqual(append["summary"], "capture retrieval answer")
            self.assertFalse(append["journal_written"])

            status = run_grasp_json(
                "--store",
                store,
                "--project",
                project,
                "--json",
                "write-status",
                "--output",
                vault,
                "--no-journal",
                "--strict",
            )
            self.assertTrue(status["strict_ok"])
