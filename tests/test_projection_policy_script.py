import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_projection_policy.py"


class ProjectionPolicyScriptTests(unittest.TestCase):
    def run_script(self, payload):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )

    def test_accepts_clean_sqlite_projection_policy(self):
        completed = self.run_script(
            {
                "ok": True,
                "projection_policy": {
                    "authority": "sqlite",
                    "base": "stored_markdown_lines",
                    "output_role": "git_tracked_projection",
                    "write_mode": "check",
                    "generated_overlays": [],
                },
            }
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("projection_policy ok", completed.stdout)

    def test_rejects_dirty_projection_even_with_matching_policy(self):
        completed = self.run_script(
            {
                "ok": False,
                "changed_files": ["A.md"],
                "projection_policy": {
                    "authority": "sqlite",
                    "base": "stored_markdown_lines",
                    "output_role": "git_tracked_projection",
                    "write_mode": "check",
                    "generated_overlays": [],
                },
            }
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("projection is not clean", completed.stderr)

    def test_rejects_non_sqlite_authority(self):
        completed = self.run_script(
            {
                "ok": True,
                "projection_policy": {
                    "authority": "markdown",
                    "base": "stored_markdown_lines",
                    "output_role": "git_tracked_projection",
                    "write_mode": "check",
                    "generated_overlays": [],
                },
            }
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("projection_policy.authority", completed.stderr)


if __name__ == "__main__":
    unittest.main()
