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
        "sqlite_last_event": {
            "event_id": "evt-1",
            "event_type": "page_update",
            "session_id": "file-back-session",
        },
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
    def run_with_fake_commands(
        self,
        fake_run_command,
        *,
        require_journal=True,
        semantic_log_check=True,
        require_session=True,
        expected_session_id="file-back-session",
        require_preflight_stamp=False,
        require_file_back_lock=False,
    ):
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
                require_session=require_session,
                expected_session_id=expected_session_id,
                require_preflight_stamp=require_preflight_stamp,
                require_file_back_lock=require_file_back_lock,
            )
        finally:
            postwrite.run_command = original_run_command

    def test_postwrite_rejects_mixed_store_output_before_other_guards(self):
        original_run_command = postwrite.run_command

        def fake_run_command(args, *, cwd):
            self.fail(f"pair guard should run before command: {args}")

        try:
            postwrite.run_command = fake_run_command
            errors = postwrite.run_postwrite_checks(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="/tmp/wiki",
                require_journal=False,
                lint=True,
                diff_check=True,
                semantic_log_check=True,
                require_session=True,
                expected_session_id="file-back-session",
                require_preflight_stamp=True,
                require_file_back_lock=True,
            )
        finally:
            postwrite.run_command = original_run_command

        self.assertEqual(len(errors), 1)
        self.assertIn("mixed file-back store/output pair", errors[0])

    def test_postwrite_checks_and_releases_file_back_lock_after_clean_checks(self):
        calls = []
        original_run_command = postwrite.run_command
        original_lock_check = postwrite.run_file_back_lock_check
        original_release = postwrite.release_file_back_lock

        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                calls.append("status")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    calls.append("semantic")
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                calls.append("projection")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            if args[-1] in {"scripts/lint_wiki.py", "--check"}:
                calls.append(args[-1])
                return subprocess.CompletedProcess(args, 0, "", "")
            self.fail(f"unexpected command: {args}")

        def fake_lock_check(path, *, expected_session_id, store, project, output):
            calls.append(("lock", path, expected_session_id, store, project, output))
            return []

        def fake_release(path, *, expected_session_id):
            calls.append(("release", path, expected_session_id))
            return []

        try:
            postwrite.run_command = fake_run_command
            postwrite.run_file_back_lock_check = fake_lock_check
            postwrite.release_file_back_lock = fake_release
            errors = postwrite.run_postwrite_checks(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                lint=True,
                diff_check=True,
                semantic_log_check=True,
                require_session=True,
                expected_session_id="file-back-session",
                require_preflight_stamp=False,
                require_file_back_lock=True,
            )
        finally:
            postwrite.run_command = original_run_command
            postwrite.run_file_back_lock_check = original_lock_check
            postwrite.release_file_back_lock = original_release

        self.assertEqual(errors, [])
        self.assertEqual(calls[0][0], "lock")
        self.assertEqual(calls[0][1], Path("/repo/.grasp/file-back.lock.json"))
        self.assertEqual(calls[-1][0], "release")
        self.assertEqual(calls[-1][2], "file-back-session")

    def test_postwrite_keeps_file_back_lock_when_checks_fail(self):
        original_run_command = postwrite.run_command
        original_lock_check = postwrite.run_file_back_lock_check
        original_release = postwrite.release_file_back_lock

        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                payload = clean_projection()
                payload["ok"] = False
                return subprocess.CompletedProcess(args, 1, json.dumps(payload), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        def fake_release(*args, **kwargs):
            self.fail("lock should not be released when postwrite checks fail")

        try:
            postwrite.run_command = fake_run_command
            postwrite.run_file_back_lock_check = lambda *args, **kwargs: []
            postwrite.release_file_back_lock = fake_release
            errors = postwrite.run_postwrite_checks(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                lint=False,
                diff_check=False,
                semantic_log_check=False,
                require_session=True,
                expected_session_id="file-back-session",
                require_preflight_stamp=False,
                require_file_back_lock=True,
            )
        finally:
            postwrite.run_command = original_run_command
            postwrite.run_file_back_lock_check = original_lock_check
            postwrite.release_file_back_lock = original_release

        self.assertTrue(errors)

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

    def test_postwrite_rejects_missing_expected_session_id(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_write_status()), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        errors = self.run_with_fake_commands(fake_run_command, expected_session_id="")

        self.assertTrue(any("GRASP_SESSION_ID" in error for error in errors))

    def test_postwrite_rejects_empty_latest_event_session_id(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                payload = clean_write_status()
                payload["sqlite_last_event"]["session_id"] = ""
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        errors = self.run_with_fake_commands(fake_run_command)

        self.assertTrue(any("empty session_id" in error for error in errors))

    def test_postwrite_rejects_latest_event_session_mismatch(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                payload = clean_write_status()
                payload["sqlite_last_event"]["session_id"] = "other-session"
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        errors = self.run_with_fake_commands(fake_run_command)

        self.assertTrue(any("expected 'file-back-session'" in error for error in errors))

    def test_postwrite_can_skip_session_check_for_legacy_audits(self):
        def fake_run_command(args, *, cwd):
            if "write-status" in args:
                payload = clean_write_status()
                payload["sqlite_last_event"]["session_id"] = ""
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            if "export-markdown" in args:
                if "--regenerate-log" in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps(clean_semantic_log_projection()), "")
                return subprocess.CompletedProcess(args, 0, json.dumps(clean_projection()), "")
            return subprocess.CompletedProcess(args, 0, "", "")

        self.assertEqual(
            self.run_with_fake_commands(
                fake_run_command,
                require_session=False,
                expected_session_id="",
            ),
            [],
        )

    def test_preflight_stamp_errors_accepts_matching_stamp(self):
        stamp = {
            "schema_version": postwrite.PREFLIGHT_STAMP_SCHEMA_VERSION,
            "kind": postwrite.PREFLIGHT_STAMP_KIND,
            "session_id": "file-back-session",
            "head": "abc123",
            "base": "origin/main",
            "base_oid": "def456",
            "sqlite_event_sequence": 10,
            "store": ".grasp/file-back.sqlite",
            "project": "grasp-wiki",
            "output": "wiki",
        }

        errors = postwrite.preflight_stamp_errors(
            stamp,
            expected_session_id="file-back-session",
            current_head="abc123",
            current_base_oid="def456",
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
        )

        self.assertEqual(errors, [])

    def test_preflight_stamp_errors_accepts_skipped_base(self):
        stamp = {
            "schema_version": postwrite.PREFLIGHT_STAMP_SCHEMA_VERSION,
            "kind": postwrite.PREFLIGHT_STAMP_KIND,
            "session_id": "file-back-session",
            "head": "abc123",
            "base": "skipped",
            "base_oid": None,
            "sqlite_event_sequence": None,
            "store": ".grasp/file-back.sqlite",
            "project": "grasp-wiki",
            "output": "wiki",
        }

        errors = postwrite.preflight_stamp_errors(
            stamp,
            expected_session_id="file-back-session",
            current_head="abc123",
            current_base_oid=None,
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
        )

        self.assertEqual(errors, [])

    def test_preflight_stamp_errors_rejects_session_head_base_and_context_mismatch(self):
        stamp = {
            "schema_version": 0,
            "kind": "other",
            "session_id": "other-session",
            "head": "old-head",
            "base": "origin/main",
            "base_oid": "old-base",
            "sqlite_event_sequence": "bad",
            "store": "other.sqlite",
            "project": "other-project",
            "output": "other-output",
        }

        errors = postwrite.preflight_stamp_errors(
            stamp,
            expected_session_id="file-back-session",
            current_head="new-head",
            current_base_oid="new-base",
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
        )
        joined = "\n".join(errors)

        self.assertIn("schema_version", joined)
        self.assertIn("kind", joined)
        self.assertIn("session_id", joined)
        self.assertIn("current HEAD", joined)
        self.assertIn("current base origin/main", joined)
        self.assertIn("sqlite_event_sequence", joined)
        self.assertIn("store", joined)
        self.assertIn("project", joined)
        self.assertIn("output", joined)

    def test_preflight_stamp_errors_require_expected_session_id(self):
        stamp = {
            "schema_version": postwrite.PREFLIGHT_STAMP_SCHEMA_VERSION,
            "kind": postwrite.PREFLIGHT_STAMP_KIND,
            "session_id": "file-back-session",
            "head": "abc123",
            "base": "skipped",
            "base_oid": None,
            "sqlite_event_sequence": 10,
            "store": ".grasp/file-back.sqlite",
            "project": "grasp-wiki",
            "output": "wiki",
        }

        errors = postwrite.preflight_stamp_errors(
            stamp,
            expected_session_id="",
            current_head="abc123",
            current_base_oid=None,
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
        )

        self.assertTrue(any("GRASP_SESSION_ID" in error for error in errors))

    def test_preflight_stamp_errors_rejects_missing_base(self):
        stamp = {
            "schema_version": postwrite.PREFLIGHT_STAMP_SCHEMA_VERSION,
            "kind": postwrite.PREFLIGHT_STAMP_KIND,
            "session_id": "file-back-session",
            "head": "abc123",
            "store": ".grasp/file-back.sqlite",
            "project": "grasp-wiki",
            "output": "wiki",
        }

        errors = postwrite.preflight_stamp_errors(
            stamp,
            expected_session_id="file-back-session",
            current_head="abc123",
            current_base_oid=None,
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
        )

        self.assertTrue(any("base is missing" in error for error in errors))
        self.assertTrue(any("sqlite_event_sequence is missing" in error for error in errors))

    def test_file_back_session_window_accepts_all_events_after_preflight_with_expected_session(self):
        errors = postwrite.file_back_session_window_errors(
            [
                {"event_sequence": 9, "event_id": "old", "session_id": "old-session"},
                {"event_sequence": 10, "event_id": "baseline", "session_id": "baseline-session"},
                {"event_sequence": 11, "event_id": "page", "session_id": "file-back-session"},
                {"event_sequence": 12, "event_id": "log", "session_id": "file-back-session"},
            ],
            expected_session_id="file-back-session",
            after_event_sequence=10,
        )

        self.assertEqual(errors, [])

    def test_file_back_session_window_rejects_intermediate_missing_or_mismatched_session(self):
        errors = postwrite.file_back_session_window_errors(
            [
                {"event_sequence": 10, "event_id": "baseline", "session_id": "old-session"},
                {"event_sequence": 11, "event_id": "page-a", "session_id": "file-back-session"},
                {"event_sequence": 12, "event_id": "page-b", "session_id": ""},
                {"event_sequence": 13, "event_id": "log", "session_id": "file-back-session"},
                {"event_sequence": 14, "event_id": "page-c", "session_id": "other-session"},
            ],
            expected_session_id="file-back-session",
            after_event_sequence=10,
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("missing or mismatched session_id", errors[0])
        self.assertIn("bad_events=2/4", errors[0])
        self.assertIn("first_bad_sequence=12", errors[0])
        self.assertIn("last_bad_sequence=14", errors[0])

    def test_file_back_session_window_rejects_no_events_after_preflight(self):
        errors = postwrite.file_back_session_window_errors(
            [
                {"event_sequence": 10, "event_id": "baseline", "session_id": "old-session"},
            ],
            expected_session_id="file-back-session",
            after_event_sequence=10,
        )

        self.assertEqual(
            errors,
            ["no SQLite events were written after preflight baseline event_sequence=10"],
        )

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
