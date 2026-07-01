import json
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import check_file_back_preflight as preflight


class FileBackPreflightScriptTests(unittest.TestCase):
    def test_dirty_path_errors_accepts_clean_status(self):
        self.assertEqual(preflight.dirty_path_errors(""), [])

    def test_dirty_path_errors_rejects_file_back_path_changes(self):
        errors = preflight.dirty_path_errors(" M wiki/log.md\n?? wiki/new.md\n")

        self.assertEqual(len(errors), 1)
        self.assertIn("dirty file-back paths", errors[0])
        self.assertIn("wiki/log.md", errors[0])
        self.assertIn("wiki/new.md", errors[0])

    def test_recovery_ladder_hints_route_common_guard_failures(self):
        hints = preflight.recovery_ladder_hints(
            [
                "dirty file-back paths before file-back:\n M wiki/log.md",
                "write-status semantic_log_stale is true",
                "current HEAD='new' differs from preflight stamp head='old'",
                "SQLite events changed after preflight before write-start",
            ],
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
        )
        joined = "\n".join(hints)

        self.assertIn("recovery ladder:", hints[0])
        self.assertIn("activity --limit 20", joined)
        self.assertIn("claims --include-expired", joined)
        self.assertIn("dirty projection/worktree", joined)
        self.assertIn("branch/HEAD moved", joined)
        self.assertIn("semantic log drift", joined)
        self.assertIn("store advanced after preflight", joined)

    def test_recovery_ladder_hints_route_pair_lock_and_session_failures(self):
        hints = preflight.recovery_ladder_hints(
            [
                "mixed file-back store/output pair",
                "session_id already exists before file-back",
                "another file-back lock is active",
            ],
            store="/tmp/store.sqlite",
            project="grasp-wiki",
            output="/tmp/wiki",
        )
        joined = "\n".join(hints)

        self.assertIn("store/output pair mismatch", joined)
        self.assertIn("reused session_id", joined)
        self.assertIn("active lock", joined)
        self.assertIn("rerun postwrite", joined)
        self.assertIn("lock owner's GRASP_SESSION_ID", joined)

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

    def test_resolve_git_base_keeps_explicit_base(self):
        original_run_command = preflight.run_command

        def fake_run_command(args, *, cwd):
            self.fail(f"unexpected command: {args}")

        try:
            preflight.run_command = fake_run_command
            base = preflight.resolve_git_base(Path("."), "origin/main")
        finally:
            preflight.run_command = original_run_command

        self.assertEqual(base, "origin/main")

    def test_resolve_git_base_auto_prefers_current_upstream(self):
        original_run_command = preflight.run_command

        def fake_run_command(args, *, cwd):
            self.assertEqual(args[-1], "@{upstream}")
            return subprocess.CompletedProcess(args, 0, "origin/codex/work\n", "")

        try:
            preflight.run_command = fake_run_command
            base = preflight.resolve_git_base(Path("."), "auto")
        finally:
            preflight.run_command = original_run_command

        self.assertEqual(base, "origin/codex/work")

    def test_resolve_git_base_auto_falls_back_to_origin_main_without_upstream(self):
        original_run_command = preflight.run_command

        def fake_run_command(args, *, cwd):
            if args[:3] == ["git", "branch", "--show-current"]:
                return subprocess.CompletedProcess(args, 0, "main\n", "")
            return subprocess.CompletedProcess(args, 128, "", "no upstream")

        try:
            preflight.run_command = fake_run_command
            base = preflight.resolve_git_base(Path("."), "auto")
        finally:
            preflight.run_command = original_run_command

        self.assertEqual(base, "origin/main")

    def test_resolve_git_base_auto_prefers_origin_current_branch_without_upstream(self):
        original_run_command = preflight.run_command

        def fake_run_command(args, *, cwd):
            if args[-1] == "@{upstream}":
                return subprocess.CompletedProcess(args, 128, "", "no upstream")
            if args[:3] == ["git", "branch", "--show-current"]:
                return subprocess.CompletedProcess(args, 0, "codex/work\n", "")
            if args[-1] == "origin/codex/work":
                return subprocess.CompletedProcess(args, 0, "abc123\n", "")
            self.fail(f"unexpected command: {args}")

        try:
            preflight.run_command = fake_run_command
            base = preflight.resolve_git_base(Path("."), "auto")
        finally:
            preflight.run_command = original_run_command

        self.assertEqual(base, "origin/codex/work")

    def test_resolve_git_base_auto_uses_head_for_no_upstream_feature_branch(self):
        original_run_command = preflight.run_command

        def fake_run_command(args, *, cwd):
            if args[-1] == "@{upstream}":
                return subprocess.CompletedProcess(args, 128, "", "no upstream")
            if args[:3] == ["git", "branch", "--show-current"]:
                return subprocess.CompletedProcess(args, 0, "codex/work\n", "")
            if args[-1] == "origin/codex/work":
                return subprocess.CompletedProcess(args, 1, "", "")
            self.fail(f"unexpected command: {args}")

        try:
            preflight.run_command = fake_run_command
            base = preflight.resolve_git_base(Path("."), "auto")
        finally:
            preflight.run_command = original_run_command

        self.assertEqual(base, "HEAD")

    def test_file_back_store_output_pair_accepts_default_pair(self):
        errors = preflight.file_back_store_output_pair_errors(
            Path("/repo"),
            store=".grasp/file-back.sqlite",
            output="wiki",
        )

        self.assertEqual(errors, [])

    def test_file_back_store_output_pair_accepts_temp_pair(self):
        errors = preflight.file_back_store_output_pair_errors(
            Path("/repo"),
            store="/tmp/file-back.sqlite",
            output="/tmp/wiki",
        )

        self.assertEqual(errors, [])

    def test_file_back_store_output_pair_rejects_default_store_temp_output(self):
        errors = preflight.file_back_store_output_pair_errors(
            Path("/repo"),
            store=".grasp/file-back.sqlite",
            output="/tmp/wiki",
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("mixed file-back store/output pair", errors[0])
        self.assertIn("temporary output against the repo file-back store", errors[0])

    def test_file_back_store_output_pair_rejects_temp_store_default_output(self):
        errors = preflight.file_back_store_output_pair_errors(
            Path("/repo"),
            store="/tmp/file-back.sqlite",
            output="wiki",
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("mixed file-back store/output pair", errors[0])

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
                "semantic_log_stale": True,
                "semantic_log_error": "boom",
                "semantic_log_policy_errors": ["bad overlay"],
            }
        )

        self.assertIn("strict_ok", "\n".join(errors))
        self.assertIn("projection ok", "\n".join(errors))
        self.assertIn("journal_exists", "\n".join(errors))
        self.assertIn("event_streams_match", "\n".join(errors))
        self.assertIn("journal_log_stale", "\n".join(errors))
        self.assertIn("semantic_log_stale", "\n".join(errors))
        self.assertIn("semantic_log_error", "\n".join(errors))
        self.assertIn("semantic_log_policy_errors", "\n".join(errors))

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

    def test_session_uniqueness_errors_require_expected_session_id(self):
        errors = preflight.session_uniqueness_errors(
            [],
            expected_session_id="",
        )

        self.assertEqual(errors, ["GRASP_SESSION_ID or --session-id is required before file-back"])

    def test_session_uniqueness_errors_accept_unused_session_id(self):
        errors = preflight.session_uniqueness_errors(
            [
                {"event_sequence": 1, "session_id": "old-session"},
                {"event_sequence": 2, "session_id": ""},
            ],
            expected_session_id="new-session",
        )

        self.assertEqual(errors, [])

    def test_session_uniqueness_errors_reject_reused_session_id(self):
        errors = preflight.session_uniqueness_errors(
            [
                {"event_sequence": 1, "session_id": "work-1"},
                {"event_sequence": 2, "session_id": "other"},
                {"event_sequence": 3, "session_id": "work-1"},
            ],
            expected_session_id="work-1",
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("session_id already exists", errors[0])
        self.assertIn("work-1", errors[0])
        self.assertIn("first_sequence=1", errors[0])
        self.assertIn("last_sequence=3", errors[0])

    def test_session_uniqueness_errors_accept_prior_active_claims_for_same_session(self):
        errors = preflight.session_uniqueness_errors(
            [
                {
                    "event_sequence": 1,
                    "event_id": "claim-a",
                    "event_type": "page_claim",
                    "session_id": "work-1",
                    "payload": {"expires_at": "2026-07-02T01:30:00+00:00"},
                },
                {
                    "event_sequence": 2,
                    "event_id": "claim-b",
                    "event_type": "page_claim",
                    "session_id": "work-1",
                    "payload": {"expires_at": "2026-07-02T01:30:00+00:00"},
                },
            ],
            expected_session_id="work-1",
            now=datetime(2026, 7, 2, 1, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(errors, [])

    def test_session_uniqueness_errors_reject_prior_claim_after_write_event(self):
        errors = preflight.session_uniqueness_errors(
            [
                {
                    "event_sequence": 1,
                    "event_id": "claim-a",
                    "event_type": "page_claim",
                    "session_id": "work-1",
                    "payload": {"expires_at": "2026-07-02T01:30:00+00:00"},
                },
                {
                    "event_sequence": 2,
                    "event_id": "page-a",
                    "event_type": "page_update",
                    "session_id": "work-1",
                },
            ],
            expected_session_id="work-1",
            now=datetime(2026, 7, 2, 1, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("session_id already exists", errors[0])

    def test_session_uniqueness_errors_reject_expired_or_released_prior_claim(self):
        now = datetime(2026, 7, 2, 1, 0, tzinfo=timezone.utc)

        expired_errors = preflight.session_uniqueness_errors(
            [
                {
                    "event_sequence": 1,
                    "event_id": "claim-a",
                    "event_type": "page_claim",
                    "session_id": "work-1",
                    "payload": {"expires_at": "2026-07-02T00:59:00+00:00"},
                },
            ],
            expected_session_id="work-1",
            now=now,
        )
        released_errors = preflight.session_uniqueness_errors(
            [
                {
                    "event_sequence": 1,
                    "event_id": "claim-a",
                    "event_type": "page_claim",
                    "session_id": "work-1",
                    "payload": {"expires_at": "2026-07-02T01:30:00+00:00"},
                },
                {
                    "event_sequence": 2,
                    "event_id": "release-a",
                    "event_type": "page_claim_release",
                    "session_id": "other-session",
                    "payload": {"claim_event_id": "claim-a"},
                },
            ],
            expected_session_id="work-1",
            now=now,
        )

        self.assertEqual(len(expired_errors), 1)
        self.assertIn("session_id already exists", expired_errors[0])
        self.assertEqual(len(released_errors), 1)
        self.assertIn("session_id already exists", released_errors[0])

    def test_session_uniqueness_errors_can_be_skipped_for_legacy_audits(self):
        errors = preflight.session_uniqueness_errors(
            [{"event_sequence": 1, "session_id": "work-1"}],
            expected_session_id="",
            skip_session_uniqueness_check=True,
        )

        self.assertEqual(errors, [])

    def test_preflight_stamp_payload_records_git_and_file_back_context(self):
        payload = preflight.preflight_stamp_payload(
            session_id="file-back-session",
            head="abc123",
            base="origin/main",
            base_oid="def456",
            sqlite_event_sequence=42,
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
            journal_mode="none",
            created_at="2026-06-27T00:00:00Z",
        )

        self.assertEqual(payload["schema_version"], preflight.PREFLIGHT_STAMP_SCHEMA_VERSION)
        self.assertEqual(payload["kind"], preflight.PREFLIGHT_STAMP_KIND)
        self.assertEqual(payload["session_id"], "file-back-session")
        self.assertEqual(payload["head"], "abc123")
        self.assertEqual(payload["base"], "origin/main")
        self.assertEqual(payload["base_oid"], "def456")
        self.assertEqual(payload["sqlite_event_sequence"], 42)
        self.assertEqual(payload["store"], ".grasp/file-back.sqlite")
        self.assertEqual(payload["project"], "grasp-wiki")
        self.assertEqual(payload["output"], "wiki")
        self.assertEqual(payload["journal_mode"], "none")

    def test_preflight_stamp_payload_marks_skipped_base(self):
        payload = preflight.preflight_stamp_payload(
            session_id="file-back-session",
            head="abc123",
            base=None,
            base_oid=None,
            sqlite_event_sequence=None,
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
            journal_mode="none",
            created_at="2026-06-27T00:00:00Z",
        )

        self.assertEqual(payload["base"], "skipped")
        self.assertIsNone(payload["base_oid"])

    def test_write_preflight_stamp_creates_parent_and_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stamp_path = Path(tmpdir) / ".grasp" / "file-back-preflight.json"
            payload = preflight.preflight_stamp_payload(
                session_id="file-back-session",
                head="abc123",
                base="origin/main",
                base_oid="def456",
                sqlite_event_sequence=9,
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                output="wiki",
                journal_mode="none",
                created_at="2026-06-27T00:00:00Z",
            )

            preflight.write_preflight_stamp(stamp_path, payload)

            self.assertTrue(stamp_path.exists())
            self.assertEqual(json.loads(stamp_path.read_text(encoding="utf-8")), payload)

    def test_file_back_lock_payload_records_session_and_context(self):
        payload = preflight.file_back_lock_payload(
            session_id="file-back-session",
            store=".grasp/file-back.sqlite",
            project="grasp-wiki",
            output="wiki",
            created_at="2026-06-28T00:00:00Z",
        )

        self.assertEqual(payload["schema_version"], preflight.FILE_BACK_LOCK_SCHEMA_VERSION)
        self.assertEqual(payload["kind"], preflight.FILE_BACK_LOCK_KIND)
        self.assertEqual(payload["session_id"], "file-back-session")
        self.assertEqual(payload["store"], ".grasp/file-back.sqlite")
        self.assertEqual(payload["project"], "grasp-wiki")
        self.assertEqual(payload["output"], "wiki")

    def test_acquire_file_back_lock_creates_lock_and_allows_same_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / ".grasp" / "file-back.lock.json"
            kwargs = {
                "session_id": "file-back-session",
                "store": ".grasp/file-back.sqlite",
                "project": "grasp-wiki",
                "output": "wiki",
            }

            self.assertEqual(preflight.acquire_file_back_lock(lock_path, **kwargs), [])
            self.assertTrue(lock_path.exists())
            self.assertEqual(preflight.acquire_file_back_lock(lock_path, **kwargs), [])

    def test_acquire_file_back_lock_rejects_other_active_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / ".grasp" / "file-back.lock.json"
            self.assertEqual(
                preflight.acquire_file_back_lock(
                    lock_path,
                    session_id="other-session",
                    store=".grasp/file-back.sqlite",
                    project="grasp-wiki",
                    output="wiki",
                ),
                [],
            )

            errors = preflight.acquire_file_back_lock(
                lock_path,
                session_id="file-back-session",
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                output="wiki",
            )

        self.assertTrue(errors)
        self.assertIn("another file-back lock is active", errors[0])
        self.assertIn("other-session", "\n".join(errors))

    def test_file_back_lock_check_and_release_require_same_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / ".grasp" / "file-back.lock.json"
            self.assertEqual(
                preflight.acquire_file_back_lock(
                    lock_path,
                    session_id="file-back-session",
                    store=".grasp/file-back.sqlite",
                    project="grasp-wiki",
                    output="wiki",
                ),
                [],
            )

            self.assertEqual(
                preflight.run_file_back_lock_check(
                    lock_path,
                    expected_session_id="file-back-session",
                    store=".grasp/file-back.sqlite",
                    project="grasp-wiki",
                    output="wiki",
                ),
                [],
            )
            errors = preflight.release_file_back_lock(lock_path, expected_session_id="other-session")
            self.assertIn("refusing to release", errors[0])
            self.assertTrue(lock_path.exists())
            self.assertEqual(preflight.release_file_back_lock(lock_path, expected_session_id="file-back-session"), [])
            self.assertFalse(lock_path.exists())

    def test_latest_event_sequence_returns_max_sequence(self):
        self.assertEqual(
            preflight.latest_event_sequence(
                [
                    {"event_sequence": 2},
                    {"event_sequence": "7"},
                    {"event_sequence": None},
                    {"event_sequence": "bad"},
                ]
            ),
            7,
        )
        self.assertIsNone(preflight.latest_event_sequence([{"event_sequence": None}]))

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

    def test_project_event_state_treats_missing_events_table_as_empty(self):
        original_project_events = preflight.project_events

        def fake_project_events(store, project):
            raise sqlite3.OperationalError("no such table: events")

        try:
            preflight.project_events = fake_project_events
            has_events, error = preflight.project_event_state(".grasp/file-back.sqlite", "grasp-wiki")
        finally:
            preflight.project_events = original_project_events

        self.assertFalse(has_events)
        self.assertIsNone(error)

    def test_project_event_state_treats_missing_store_file_as_empty(self):
        original_project_events = preflight.project_events

        def fake_project_events(store, project):
            raise sqlite3.OperationalError("unable to open database file")

        with tempfile.TemporaryDirectory() as tmpdir:
            missing_store = Path(tmpdir) / ".grasp" / "file-back.sqlite"
            try:
                preflight.project_events = fake_project_events
                has_events, error = preflight.project_event_state(str(missing_store), "grasp-wiki")
            finally:
                preflight.project_events = original_project_events

        self.assertFalse(has_events)
        self.assertIsNone(error)

    def test_project_event_state_reports_non_bootstrappable_sqlite_errors(self):
        original_project_events = preflight.project_events

        def fake_project_events(store, project):
            raise sqlite3.DatabaseError("database disk image is malformed")

        try:
            preflight.project_events = fake_project_events
            has_events, error = preflight.project_event_state(".grasp/file-back.sqlite", "grasp-wiki")
        finally:
            preflight.project_events = original_project_events

        self.assertFalse(has_events)
        self.assertIn("could not inspect file-back store events", error)
        self.assertIn("malformed", error)

    def test_project_event_state_reports_unopenable_existing_store(self):
        original_project_events = preflight.project_events

        def fake_project_events(store, project):
            raise sqlite3.OperationalError("unable to open database file")

        with tempfile.TemporaryDirectory() as tmpdir:
            existing_store = Path(tmpdir) / "file-back.sqlite"
            existing_store.write_text("not sqlite", encoding="utf-8")
            try:
                preflight.project_events = fake_project_events
                has_events, error = preflight.project_event_state(str(existing_store), "grasp-wiki")
            finally:
                preflight.project_events = original_project_events

        self.assertFalse(has_events)
        self.assertIn("could not inspect file-back store events", error)
        self.assertIn("unable to open database file", error)

    def test_bootstrap_checks_store_relative_to_repo(self):
        original_project_events = preflight.project_events
        seen_store = None

        def fake_project_events(store, project):
            nonlocal seen_store
            seen_store = store
            return [{"event_sequence": 1, "session_id": "bootstrap-file-back-store"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            try:
                preflight.project_events = fake_project_events
                errors = preflight.bootstrap_file_back_store_if_needed(
                    repo,
                    store=".grasp/file-back.sqlite",
                    project="grasp-wiki",
                    output="wiki",
                    require_journal=False,
                )
            finally:
                preflight.project_events = original_project_events

        self.assertEqual(errors, [])
        self.assertEqual(seen_store, str(repo / ".grasp" / "file-back.sqlite"))

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

    def test_run_grasp_preflight_rejects_mixed_store_output_before_import(self):
        original_run_command = preflight.run_command

        def fake_run_command(args, *, cwd):
            self.fail(f"unexpected command before pair guard: {args}")

        try:
            preflight.run_command = fake_run_command
            errors = preflight.run_grasp_preflight(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="/tmp/wiki",
                require_journal=False,
                expected_session_id="file-back-session",
            )
        finally:
            preflight.run_command = original_run_command

        self.assertEqual(len(errors), 1)
        self.assertIn("mixed file-back store/output pair", errors[0])

    def test_run_grasp_preflight_no_journal_uses_no_journal_write_status(self):
        original_run_command = preflight.run_command
        original_project_events = preflight.project_events
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
            preflight.project_events = lambda store, project: [
                {"event_sequence": 1, "session_id": "bootstrap-file-back-store"}
            ]
            errors = preflight.run_grasp_preflight(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                expected_session_id="file-back-session",
            )
        finally:
            preflight.run_command = original_run_command
            preflight.project_events = original_project_events

        self.assertEqual(errors, [])
        self.assertIsNotNone(seen_write_status_args)
        self.assertIn("--no-journal", seen_write_status_args)
        self.assertNotIn("--journal", seen_write_status_args)

    def test_run_grasp_preflight_bootstraps_empty_no_journal_store(self):
        original_run_command = preflight.run_command
        original_project_events = preflight.project_events
        seen_adopt_args = None

        def fake_run_command(args, *, cwd):
            nonlocal seen_adopt_args
            if "adopt-markdown" in args:
                seen_adopt_args = args
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps({"project": "grasp-wiki", "sqlite_events_inserted": 3}),
                    "",
                )
            if "import" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            if "write-status" in args:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps(
                        {
                            "strict_ok": True,
                            "projection": {"ok": True},
                            "journal_exists": False,
                            "event_streams_match": False,
                            "journal_log_stale": False,
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
            calls = {"count": 0}

            def fake_project_events(store, project):
                calls["count"] += 1
                if calls["count"] == 1:
                    return []
                return [{"event_sequence": 1, "session_id": "bootstrap-file-back-store"}]

            preflight.project_events = fake_project_events
            errors = preflight.run_grasp_preflight(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                expected_session_id="file-back-session",
            )
        finally:
            preflight.run_command = original_run_command
            preflight.project_events = original_project_events

        self.assertEqual(errors, [])
        self.assertIsNotNone(seen_adopt_args)
        self.assertIn("adopt-markdown", seen_adopt_args)
        self.assertIn("--journal", seen_adopt_args)
        self.assertIn(preflight.DEFAULT_FILE_BACK_BOOTSTRAP_JOURNAL, seen_adopt_args)
        self.assertIn("--replace-journal", seen_adopt_args)
        self.assertIn(preflight.DEFAULT_FILE_BACK_BOOTSTRAP_SESSION_ID, seen_adopt_args)

    def test_run_grasp_preflight_rejects_sqlite_errors_instead_of_bootstrapping(self):
        original_run_command = preflight.run_command
        original_project_events = preflight.project_events

        def fake_run_command(args, *, cwd):
            self.fail(f"unexpected bootstrap/import command after store inspection error: {args}")

        def fake_project_events(store, project):
            raise sqlite3.OperationalError("database is locked")

        try:
            preflight.run_command = fake_run_command
            preflight.project_events = fake_project_events
            errors = preflight.run_grasp_preflight(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                expected_session_id="file-back-session",
            )
        finally:
            preflight.run_command = original_run_command
            preflight.project_events = original_project_events

        self.assertEqual(len(errors), 1)
        self.assertIn("could not inspect file-back store events", errors[0])
        self.assertIn("database is locked", errors[0])

    def test_run_grasp_preflight_does_not_bootstrap_journal_mode(self):
        original_run_command = preflight.run_command
        original_project_events = preflight.project_events

        def fake_run_command(args, *, cwd):
            if "adopt-markdown" in args:
                self.fail("journal mode should not bootstrap the no-journal file-back store")
            if "import" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            if "write-status" in args:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    json.dumps(
                        {
                            "strict_ok": False,
                            "projection": {"ok": True},
                            "journal_exists": False,
                            "event_streams_match": False,
                            "journal_log_stale": False,
                        }
                    ),
                    "",
                )
            self.fail(f"unexpected command: {args}")

        try:
            preflight.run_command = fake_run_command
            preflight.project_events = lambda store, project: []
            errors = preflight.run_grasp_preflight(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal="wiki.grasp/events.jsonl",
                output="wiki",
                require_journal=True,
                expected_session_id="file-back-session",
            )
        finally:
            preflight.run_command = original_run_command
            preflight.project_events = original_project_events

        self.assertTrue(errors)
        self.assertIn("journal_exists", "\n".join(errors))

    def test_run_grasp_preflight_rejects_reused_session_id_before_projection_check(self):
        original_run_command = preflight.run_command
        original_project_events = preflight.project_events

        def fake_run_command(args, *, cwd):
            if "import" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            if "write-status" in args:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps(
                        {
                            "strict_ok": True,
                            "projection": {"ok": True},
                            "journal_exists": False,
                            "event_streams_match": False,
                            "journal_log_stale": False,
                        }
                    ),
                    "",
                )
            if "export-markdown" in args:
                self.fail("projection check should not run after session reuse failure")
            self.fail(f"unexpected command: {args}")

        try:
            preflight.run_command = fake_run_command
            preflight.project_events = lambda store, project: [
                {"event_sequence": 7, "session_id": "file-back-session"}
            ]
            errors = preflight.run_grasp_preflight(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                expected_session_id="file-back-session",
            )
        finally:
            preflight.run_command = original_run_command
            preflight.project_events = original_project_events

        self.assertEqual(len(errors), 1)
        self.assertIn("session_id already exists", errors[0])

    def test_run_grasp_preflight_accepts_prior_active_claim_for_session(self):
        original_run_command = preflight.run_command
        original_project_events = preflight.project_events
        saw_projection_check = False

        def fake_run_command(args, *, cwd):
            nonlocal saw_projection_check
            if "import" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            if "write-status" in args:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps(
                        {
                            "strict_ok": True,
                            "projection": {"ok": True},
                            "journal_exists": False,
                            "event_streams_match": False,
                            "journal_log_stale": False,
                        }
                    ),
                    "",
                )
            if "export-markdown" in args:
                saw_projection_check = True
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
            preflight.project_events = lambda store, project: [
                {
                    "event_sequence": 7,
                    "event_id": "claim-a",
                    "event_type": "page_claim",
                    "session_id": "file-back-session",
                    "payload": {"expires_at": "2999-01-01T00:00:00+00:00"},
                }
            ]
            errors = preflight.run_grasp_preflight(
                Path("."),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                expected_session_id="file-back-session",
            )
        finally:
            preflight.run_command = original_run_command
            preflight.project_events = original_project_events

        self.assertEqual(errors, [])
        self.assertTrue(saw_projection_check)


if __name__ == "__main__":
    unittest.main()
