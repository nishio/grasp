import tempfile
import unittest
from pathlib import Path

from scripts import check_file_back_runbook as runbook


class FileBackRunbookScriptTests(unittest.TestCase):
    def test_check_text_accepts_required_fragments_without_forbidden_fragments(self):
        rule = runbook.RunbookRule(
            "doc.md",
            required=("alpha", "beta"),
            forbidden=("gamma",),
        )

        self.assertEqual(runbook.check_text("alpha\nbeta\n", rule), [])

    def test_check_text_reports_missing_and_forbidden_fragments(self):
        rule = runbook.RunbookRule(
            "doc.md",
            required=("alpha", "beta"),
            forbidden=("gamma",),
        )

        errors = runbook.check_text("alpha\ngamma\n", rule)

        self.assertEqual(len(errors), 2)
        self.assertIn("missing required fragment: beta", errors[0])
        self.assertIn("forbidden stale fragment present: gamma", errors[1])

    def test_check_runbooks_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            errors = runbook.check_runbooks(
                Path(tmpdir),
                rules=(runbook.RunbookRule("missing.md", required=("alpha",)),),
            )

        self.assertEqual(errors, ["missing.md: file does not exist"])

    def test_default_runbook_rules_match_current_repo_docs(self):
        self.assertEqual(runbook.check_runbooks(Path(".")), [])


if __name__ == "__main__":
    unittest.main()
