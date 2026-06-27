import json
import subprocess
import unittest
from pathlib import Path

from scripts import check_file_back_preflight as preflight


class FileBackPreflightScriptTests(unittest.TestCase):
    def test_dirty_path_errors_accepts_clean_status(self):
        self.assertEqual(preflight.dirty_path_errors(""), [])

    def test_dirty_path_errors_rejects_wiki_or_journal_changes(self):
        errors = preflight.dirty_path_errors(" M wiki/log.md\n?? wiki/new.md\n")

        self.assertEqual(len(errors), 1)
        self.assertIn("dirty wiki/journal paths", errors[0])
        self.assertIn("wiki/log.md", errors[0])
        self.assertIn("wiki/new.md", errors[0])

    def test_base_divergence_errors_accepts_empty_left_right_log(self):
        self.assertEqual(preflight.base_divergence_errors("", "origin/main"), [])

    def test_base_divergence_errors_rejects_ahead_or_behind_commits(self):
        errors = preflight.base_divergence_errors(
            "< abc1234 remote commit\n> def5678 local commit\n",
            "origin/main",
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("branch differs from origin/main", errors[0])
        self.assertIn("remote commit", errors[0])
        self.assertIn("local commit", errors[0])

    def test_write_status_errors_accepts_clean_strict_status(self):
        self.assertEqual(
            preflight.write_status_errors(
                {
                    "strict_ok": True,
                    "projection": {"ok": True},
                    "journal_exists": True,
                    "event_streams_match": True,
                    "journal_log_stale": False,
                }
            ),
            [],
        )

    def test_write_status_errors_rejects_transition_guard_failures(self):
        errors = preflight.write_status_errors(
            {
                "strict_ok": False,
                "projection_ok": False,
                "journal_exists": False,
                "event_streams_match": False,
                "journal_log_stale": True,
            }
        )

        self.assertIn("strict_ok", "\n".join(errors))
        self.assertIn("projection ok", "\n".join(errors))
        self.assertIn("journal_exists", "\n".join(errors))
        self.assertIn("event_streams_match", "\n".join(errors))
        self.assertIn("journal_log_stale", "\n".join(errors))

    def test_parse_json_output_rejects_non_object(self):
        value, error = preflight.parse_json_output("[]", "command")

        self.assertIsNone(value)
        self.assertIn("expected object", error)

    def test_run_grasp_preflight_reports_write_status_json_errors(self):
        original_run_command = preflight.run_command

        def fake_run_command(args, *, cwd):
            if "import" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            if "write-status" in args:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    json.dumps(
                        {
                            "strict_ok": False,
                            "projection": {"ok": False},
                            "journal_exists": True,
                            "event_streams_match": False,
                            "journal_log_stale": False,
                        }
                    ),
                    "",
                )
            self.fail(f"unexpected command: {args}")

        try:
            preflight.run_command = fake_run_command
            errors = preflight.run_grasp_preflight(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal="wiki.grasp/events.jsonl",
                output="wiki",
            )
        finally:
            preflight.run_command = original_run_command

        self.assertTrue(errors)
        self.assertNotIn(None, errors)
        self.assertIn("strict_ok", "\n".join(errors))
        self.assertIn("event_streams_match", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
