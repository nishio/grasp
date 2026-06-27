import json
import subprocess
import unittest
from pathlib import Path

from scripts import check_file_back_postwrite as postwrite


def clean_write_status():
    return {
        "strict_ok": True,
        "projection": {"ok": True},
        "journal_exists": True,
        "event_streams_match": True,
        "journal_log_stale": False,
    }


def clean_projection():
    return {
        "ok": True,
        "projection_policy": {
            "authority": "sqlite",
            "base": "stored_markdown_lines",
            "output_role": "git_tracked_projection",
            "write_mode": "check",
            "generated_overlays": [],
        },
    }


def clean_semantic_log_projection():
    payload = clean_projection()
    payload.update(
        {
            "regenerated_files": ["log.md"],
            "log_event_source": "sqlite",
            "log_event_count": 3,
        }
    )
    payload["projection_policy"]["generated_overlays"] = ["sqlite-events-log"]
    return payload


class FileBackPostwriteScriptTests(unittest.TestCase):
    def run_with_fake_commands(self, fake_run_command, *, require_journal=True, semantic_log_check=True):
        original_run_command = postwrite.run_command
        try:
            postwrite.run_command = fake_run_command
            return postwrite.run_postwrite_checks(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal="wiki.grasp/events.jsonl" if require_journal else None,
                output="wiki",
                require_journal=require_journal,
                lint=True,
                diff_check=True,
                semantic_log_check=semantic_log_check,
            )
        finally:
            postwrite.run_command = original_run_command

    def test_postwrite_accepts_clean_status_projection_lint_and_diff(self):
        seen_semantic_log_args = None

        def fake_run_command(args, *, cwd):
            nonlocal seen_semantic_log_args
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    seen_semantic_log_args = args
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            if args[-1] in {"scripts/lint_wiki.py", "--check"}:
                return subprocess.CompletedProcess(args, 0, "", "")
            self.fail(f"unexpected command: {args}")

        self.assertEqual(self.run_with_fake_commands(fake_run_command), [])
        self.assertIsNotNone(seen_semantic_log_args)

    def test_postwrite_no_journal_uses_no_journal_status_and_skips_journal_guards(self):
        seen_write_status_args = None

        def fake_run_command(args, *, cwd):
            nonlocal seen_write_status_args
            if "write-status" in args:
                seen_write_status_args = args
                payload = clean_write_status()
                payload["journal_exists"] = False
                payload["event_streams_match"] = False
                payload["journal_log_stale"] = True
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            if args[-1] in {"scripts/lint_wiki.py", "--check"}:
                return subprocess.CompletedProcess(args, 0, "", "")
            self.fail(f"unexpected command: {args}")

        errors = self.run_with_fake_commands(fake_run_command, require_journal=False)

        self.assertEqual(errors, [])
        self.assertIsNotNone(seen_write_status_args)
        self.assertIn("--no-journal", seen_write_status_args)
        self.assertNotIn("--journal", seen_write_status_args)

    def test_postwrite_rejects_dirty_projection_policy(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                payload = clean_projection()
                payload["ok"] = False
                payload["changed_files"] = ["wiki/log.md"]
                return subprocess.CompletedProcess(args, 1, json.dumps(payload), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        errors = self.run_with_fake_commands(fake_run_command)

        self.assertTrue(errors)
        self.assertIn("projection is not clean", "\n".join(errors))

    def test_postwrite_rejects_lint_failure(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            if args[-1] == "scripts/lint_wiki.py":
                return subprocess.CompletedProcess(args, 1, "", "lint failed")
            if args[-1] == "--check":
                return subprocess.CompletedProcess(args, 0, "", "")
            self.fail(f"unexpected command: {args}")

        errors = self.run_with_fake_commands(fake_run_command)

        self.assertEqual(errors, ["wiki lint failed with exit 1: lint failed"])

    def test_postwrite_rejects_dirty_semantic_log_projection(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    payload = clean_semantic_log_projection()
                    payload["ok"] = False
                    payload["changed_files"] = ["log.md"]
                    return subprocess.CompletedProcess(args, 1, json.dumps(payload), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        errors = self.run_with_fake_commands(fake_run_command)

        self.assertTrue(errors)
        self.assertIn("projection is not clean", "\n".join(errors))

    def test_postwrite_rejects_non_sqlite_semantic_log_source(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    payload = clean_semantic_log_projection()
                    payload["log_event_source"] = "journal"
                    payload["projection_policy"]["generated_overlays"] = ["legacy-journal-log"]
                    return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        errors = self.run_with_fake_commands(fake_run_command)

        joined = "\n".join(errors)
        self.assertIn("log_event_source", joined)
        self.assertIn("sqlite-events-log", joined)

    def test_postwrite_can_skip_semantic_log_projection_check(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                self.assertNotIn("--regenerate-log", args)
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        self.assertEqual(
            self.run_with_fake_commands(fake_run_command, semantic_log_check=False),
            [],
        )


if __name__ == "__main__":
    unittest.main()
