import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class Mode2MarkdownReadonlyScriptTests(unittest.TestCase):
    def run_grasp(self, store: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "grasp",
                "--store",
                str(store),
                "--project",
                "wiki",
                *args,
            ],
            cwd=REPO_ROOT,
            check=check,
            text=True,
            capture_output=True,
        )

    def run_guard(self, store: Path, root: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "scripts/check_mode2_markdown_readonly.py",
                "--repo",
                str(REPO_ROOT),
                "--store",
                str(store),
                "--project",
                "wiki",
                "--output",
                str(root),
            ],
            cwd=REPO_ROOT,
            check=check,
            text=True,
            capture_output=True,
        )

    def test_clean_projection_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n- initial\n", encoding="utf-8")
            store = Path(tmpdir) / "store.sqlite"

            self.run_grasp(store, "import", "--markdown", str(root))
            guard = self.run_guard(store, root)

        self.assertIn("mode2 Markdown read-only ok", guard.stdout)

    def test_direct_markdown_edit_fails_until_explicit_reconcile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            page = root / "A.md"
            page.write_text("# A\n- initial\n", encoding="utf-8")
            store = Path(tmpdir) / "store.sqlite"

            self.run_grasp(store, "import", "--markdown", str(root))
            page.write_text("# A\n- direct edit\n", encoding="utf-8")
            dirty = self.run_guard(store, root, check=False)
            self.run_grasp(store, "reconcile-markdown", "--output", str(root), "--no-journal")
            clean = self.run_guard(store, root)

        self.assertEqual(dirty.returncode, 1)
        self.assertIn("mode2 Markdown read-only guard failed", dirty.stderr)
        self.assertIn("projection is not clean", dirty.stderr)
        self.assertIn("reconcile-markdown --output", dirty.stderr)
        self.assertIn("without --dry-run", dirty.stderr)
        self.assertIn("mode2 Markdown read-only ok", clean.stdout)


if __name__ == "__main__":
    unittest.main()
