import re
import subprocess
import sys
import unittest
from pathlib import Path

import grasp


REPO_ROOT = Path(__file__).resolve().parents[1]


class VersionMetadataTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'(?m)^version = "([^"]+)"$', pyproject)
        self.assertIsNotNone(match, "pyproject.toml must declare [project] version")
        self.assertEqual(grasp.__version__, match.group(1))

    def test_cli_version_reports_package_version(self):
        completed = subprocess.run(
            [sys.executable, "-m", "grasp", "--version"],
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.stdout.strip(), f"grasp {grasp.__version__}")
