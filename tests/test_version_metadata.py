import re
import subprocess
import sys
import unittest
from pathlib import Path

import grasp


REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "wiki" / "history.md"
IMPLEMENTED_PATH = REPO_ROOT / "wiki" / "entities" / "grasp-v1-implemented.md"


def pyproject_version() -> str:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version = "([^"]+)"$', pyproject)
    if match is None:
        raise AssertionError("pyproject.toml must declare [project] version")
    return match.group(1)


def required_match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text)
    if match is None:
        raise AssertionError(f"{label} is missing")
    return match.group(1)


class VersionMetadataTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self):
        self.assertEqual(grasp.__version__, pyproject_version())

    def test_cli_version_reports_package_version(self):
        completed = subprocess.run(
            [sys.executable, "-m", "grasp", "--version"],
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.stdout.strip(), f"grasp {grasp.__version__}")

    def test_wiki_release_ledger_matches_package_version(self):
        version = pyproject_version()
        history = HISTORY_PATH.read_text(encoding="utf-8")
        implemented = IMPLEMENTED_PATH.read_text(encoding="utf-8")

        latest_history_entry = required_match(
            r"(?m)^- `([^`]+)`（更新:",
            history,
            "latest history version entry",
        )
        history_current = required_match(
            r"(?m)^- Current public compatibility version: `([^`]+)`$",
            history,
            "history current public compatibility version",
        )
        history_package = required_match(
            r"(?m)^- Current package metadata should match `([^`]+)`;",
            history,
            "history package metadata version",
        )
        implemented_current = required_match(
            r"(?m)^- current public compatibility version は `([^`]+)`。",
            implemented,
            "grasp-v1-implemented current public compatibility version",
        )

        self.assertEqual(latest_history_entry, version)
        self.assertEqual(history_current, version)
        self.assertEqual(history_package, version)
        self.assertEqual(implemented_current, version)
