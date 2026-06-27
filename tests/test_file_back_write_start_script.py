import unittest
from pathlib import Path

from scripts import check_file_back_write_start as write_start


class FileBackWriteStartScriptTests(unittest.TestCase):
    def test_write_start_rejects_mixed_store_output_before_other_guards(self):
        original_stamp = write_start.run_preflight_stamp_check
        original_dirty = write_start.check_dirty_paths
        original_status = write_start.run_write_status
        original_projection = write_start.run_projection_check
        original_semantic = write_start.run_semantic_log_projection_check

        def unexpected(*args, **kwargs):
            self.fail("pair guard should run before other checks")

        try:
            write_start.run_preflight_stamp_check = unexpected
            write_start.check_dirty_paths = unexpected
            write_start.run_write_status = unexpected
            write_start.run_projection_check = unexpected
            write_start.run_semantic_log_projection_check = unexpected
            errors = write_start.run_write_start_checks(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="/tmp/wiki",
                require_journal=False,
                dirty_paths=("wiki",),
                expected_session_id="file-back-session",
            )
        finally:
            write_start.run_preflight_stamp_check = original_stamp
            write_start.check_dirty_paths = original_dirty
            write_start.run_write_status = original_status
            write_start.run_projection_check = original_projection
            write_start.run_semantic_log_projection_check = original_semantic

        self.assertEqual(len(errors), 1)
        self.assertIn("mixed file-back store/output pair", errors[0])

    def test_write_start_runs_stamp_dirty_status_projection_and_semantic_checks(self):
        calls = []
        original_stamp = write_start.run_preflight_stamp_check
        original_dirty = write_start.check_dirty_paths
        original_status = write_start.run_write_status
        original_projection = write_start.run_projection_check
        original_semantic = write_start.run_semantic_log_projection_check

        def fake_stamp(repo, *, stamp_path, expected_session_id, store, project, output):
            calls.append(("stamp", repo, stamp_path, expected_session_id, store, project, output))
            return []

        def fake_dirty(repo, paths):
            calls.append(("dirty", repo, paths))
            return []

        def fake_status(repo, **kwargs):
            calls.append(("status", repo, kwargs))
            return []

        def fake_projection(repo, **kwargs):
            calls.append(("projection", repo, kwargs))
            return []

        def fake_semantic(repo, **kwargs):
            calls.append(("semantic", repo, kwargs))
            return []

        try:
            write_start.run_preflight_stamp_check = fake_stamp
            write_start.check_dirty_paths = fake_dirty
            write_start.run_write_status = fake_status
            write_start.run_projection_check = fake_projection
            write_start.run_semantic_log_projection_check = fake_semantic
            errors = write_start.run_write_start_checks(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                dirty_paths=("wiki",),
                expected_session_id="file-back-session",
            )
        finally:
            write_start.run_preflight_stamp_check = original_stamp
            write_start.check_dirty_paths = original_dirty
            write_start.run_write_status = original_status
            write_start.run_projection_check = original_projection
            write_start.run_semantic_log_projection_check = original_semantic

        self.assertEqual(errors, [])
        self.assertEqual([call[0] for call in calls], ["stamp", "dirty", "status", "projection", "semantic"])
        self.assertEqual(calls[0][2], Path("/repo/.grasp/file-back-preflight.json"))
        self.assertEqual(calls[0][3], "file-back-session")
        status_kwargs = calls[2][2]
        self.assertFalse(status_kwargs["require_journal"])
        self.assertFalse(status_kwargs["require_session"])
        self.assertEqual(status_kwargs["expected_session_id"], "")

    def test_write_start_can_skip_stamp_and_semantic_for_legacy_audits(self):
        calls = []
        original_stamp = write_start.run_preflight_stamp_check
        original_dirty = write_start.check_dirty_paths
        original_status = write_start.run_write_status
        original_projection = write_start.run_projection_check
        original_semantic = write_start.run_semantic_log_projection_check

        def unexpected_stamp(*args, **kwargs):
            self.fail("stamp check should be skipped")

        def fake_dirty(repo, paths):
            calls.append("dirty")
            return []

        def fake_status(repo, **kwargs):
            calls.append("status")
            return []

        def fake_projection(repo, **kwargs):
            calls.append("projection")
            return []

        def unexpected_semantic(*args, **kwargs):
            self.fail("semantic log check should be skipped")

        try:
            write_start.run_preflight_stamp_check = unexpected_stamp
            write_start.check_dirty_paths = fake_dirty
            write_start.run_write_status = fake_status
            write_start.run_projection_check = fake_projection
            write_start.run_semantic_log_projection_check = unexpected_semantic
            errors = write_start.run_write_start_checks(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
                require_preflight_stamp=False,
                semantic_log_check=False,
            )
        finally:
            write_start.run_preflight_stamp_check = original_stamp
            write_start.check_dirty_paths = original_dirty
            write_start.run_write_status = original_status
            write_start.run_projection_check = original_projection
            write_start.run_semantic_log_projection_check = original_semantic

        self.assertEqual(errors, [])
        self.assertEqual(calls, ["dirty", "status", "projection"])

    def test_write_start_accumulates_errors_from_all_guards(self):
        original_stamp = write_start.run_preflight_stamp_check
        original_dirty = write_start.check_dirty_paths
        original_status = write_start.run_write_status
        original_projection = write_start.run_projection_check
        original_semantic = write_start.run_semantic_log_projection_check

        try:
            write_start.run_preflight_stamp_check = lambda *args, **kwargs: ["stamp error"]
            write_start.check_dirty_paths = lambda *args, **kwargs: ["dirty error"]
            write_start.run_write_status = lambda *args, **kwargs: ["status error"]
            write_start.run_projection_check = lambda *args, **kwargs: ["projection error"]
            write_start.run_semantic_log_projection_check = lambda *args, **kwargs: ["semantic error"]
            errors = write_start.run_write_start_checks(
                Path("/repo"),
                store=".grasp/file-back.sqlite",
                project="grasp-wiki",
                journal=None,
                output="wiki",
                require_journal=False,
            )
        finally:
            write_start.run_preflight_stamp_check = original_stamp
            write_start.check_dirty_paths = original_dirty
            write_start.run_write_status = original_status
            write_start.run_projection_check = original_projection
            write_start.run_semantic_log_projection_check = original_semantic

        self.assertEqual(
            errors,
            ["stamp error", "dirty error", "status error", "projection error", "semantic error"],
        )


if __name__ == "__main__":
    unittest.main()
