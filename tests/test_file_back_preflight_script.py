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

    def test_write_status_errors_no_journal_ignores_journal_guards(self):
        errors = preflight.write_status_errors(
            {
                "strict_ok": True,
                "projection": {"ok": True},
                "journal_exists": False,
                "event_streams_match": False,
                "journal_log_stale": True,
            },
            require_journal=False,
        )

        self.assertEqual(errors, [])

    def test_write_status_command_selects_journal_or_no_journal_mode(self):
        journal_command = preflight.write_status_command(
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            journal="wiki.grasp/events.jsonl",
            output="wiki",
            require_journal=True,
        )
        no_journal_command = preflight.write_status_command(
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            journal=None,
            output="wiki",
            require_journal=False,
        )

        self.assertIn("--journal", journal_command)
        self.assertIn("wiki.grasp/events.jsonl", journal_command)
        self.assertNotIn("--no-journal", journal_command)
        self.assertIn("--no-journal", no_journal_command)
        self.assertNotIn("--journal", no_journal_command)

    def test_write_status_command_requires_journal_path_in_journal_mode(self):
        with self.assertRaisesRegex(ValueError, "journal path is required"):
            preflight.write_status_command(
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=True,
            )

    def test_resolve_require_journal_defaults_to_no_journal(self):
        self.assertFalse(preflight.resolve_require_journal(no_journal=False, with_journal=False))
        self.assertFalse(preflight.resolve_require_journal(no_journal=True, with_journal=False))
        self.assertTrue(preflight.resolve_require_journal(no_journal=False, with_journal=True))

    def test_resolve_require_journal_rejects_conflicting_flags(self):
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            preflight.resolve_require_journal(no_journal=True, with_journal=True)

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

    def test_run_grasp_preflight_no_journal_uses_no_journal_write_status(self):
        original_run_command = preflight.run_command
        seen_write_status_args = None

        def fake_run_command(args, *, cwd):
            nonlocal seen_write_status_args
            if "import" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            if "write-status" in args:
                seen_write_status_args = args
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps(
                        {
                            "strict_ok": True,
                            "projection": {"ok": True},
                            "journal_exists": False,
                            "event_streams_match": False,
                            "journal_log_stale": True,
                        }
                    ),
                    "",
                )
            if "export-markdown" in args:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps(
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
                journal=None,
                output="wiki",
                require_journal=False,
            )
        finally:
            preflight.run_command = original_run_command

        self.assertEqual(errors, [])
        self.assertIsNotNone(seen_write_status_args)
        self.assertIn("--no-journal", seen_write_status_args)
        self.assertNotIn("--journal", seen_write_status_args)


if __name__ == "__main__":
    unittest.main()
