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

    def test_default_rules_reject_stale_guard_flag_spelling(self):
        stale_text = """
python3 scripts/check_file_back_preflight.py --no-journal
python3 scripts/check_file_back_postwrite.py --no-journal
"""

        errors = runbook.check_text(stale_text, runbook.DEFAULT_RULES[0])

        self.assertTrue(any("check_file_back_preflight.py --no-journal" in error for error in errors))
        self.assertTrue(any("check_file_back_postwrite.py --no-journal" in error for error in errors))

    def test_default_rules_reject_repo_with_journal_runbook(self):
        stale_text = """
python3 scripts/check_file_back_preflight.py --with-journal
python3 scripts/check_file_back_postwrite.py --with-journal
--journal wiki.grasp/events.jsonl --output wiki
"""

        errors = runbook.check_text(stale_text, runbook.DEFAULT_RULES[0])

        self.assertTrue(any("check_file_back_preflight.py --with-journal" in error for error in errors))
        self.assertTrue(any("check_file_back_postwrite.py --with-journal" in error for error in errors))
        self.assertTrue(any("--journal wiki.grasp/events.jsonl --output wiki" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
