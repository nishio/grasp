import subprocess
import unittest
from pathlib import Path

from scripts import check_push_ownership as push_guard


class PushOwnershipScriptTests(unittest.TestCase):
    def test_dirty_worktree_errors_accepts_clean_status(self):
        self.assertEqual(push_guard.dirty_worktree_errors(""), [])

    def test_dirty_worktree_errors_rejects_any_dirty_file(self):
        errors = push_guard.dirty_worktree_errors(" M grasp/cli.py\n?? tmp.md\n")

        self.assertEqual(len(errors), 1)
        self.assertIn("dirty worktree", errors[0])
        self.assertIn("grasp/cli.py", errors[0])
        self.assertIn("tmp.md", errors[0])

    def test_protected_branch_errors_rejects_main_by_default(self):
        errors = push_guard.protected_branch_errors(
            "main",
            protected_branches=("main", "master"),
            allow_protected_branch=False,
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("protected branch main", errors[0])

    def test_protected_branch_errors_allows_feature_branch(self):
        errors = push_guard.protected_branch_errors(
            "codex/work",
            protected_branches=("main", "master"),
            allow_protected_branch=False,
        )

        self.assertEqual(errors, [])

    def test_protected_branch_errors_can_be_overridden(self):
        errors = push_guard.protected_branch_errors(
            "main",
            protected_branches=("main", "master"),
            allow_protected_branch=True,
        )

        self.assertEqual(errors, [])

    def test_split_left_right_counts_expected_sides(self):
        left, right, other = push_guard.split_left_right(
            "< abc1234 remote commit\n> def5678 local commit\n? unexpected\n"
        )

        self.assertEqual(left, ["< abc1234 remote commit"])
        self.assertEqual(right, ["> def5678 local commit"])
        self.assertEqual(other, ["? unexpected"])

    def test_push_divergence_errors_accepts_ahead_only(self):
        errors = push_guard.push_divergence_errors("> def5678 local commit\n", "origin/work")

        self.assertEqual(errors, [])

    def test_push_divergence_errors_rejects_behind_commits(self):
        errors = push_guard.push_divergence_errors("< abc1234 remote commit\n", "origin/work")

        self.assertEqual(len(errors), 1)
        self.assertIn("behind origin/work", errors[0])
        self.assertIn("remote commit", errors[0])

    def test_resolve_push_base_keeps_explicit_base(self):
        original_run_command = push_guard.run_command

        def fake_run_command(args, *, cwd):
            self.fail(f"unexpected command: {args}")

        try:
            push_guard.run_command = fake_run_command
            base = push_guard.resolve_push_base(Path("."), "codex/work", "origin/main")
        finally:
            push_guard.run_command = original_run_command

        self.assertEqual(base, "origin/main")

    def test_resolve_push_base_auto_prefers_current_upstream(self):
        original_run_command = push_guard.run_command

        def fake_run_command(args, *, cwd):
            self.assertEqual(args[-1], "@{upstream}")
            return subprocess.CompletedProcess(args, 0, "origin/codex/work\n", "")

        try:
            push_guard.run_command = fake_run_command
            base = push_guard.resolve_push_base(Path("."), "codex/work", "auto")
        finally:
            push_guard.run_command = original_run_command

        self.assertEqual(base, "origin/codex/work")

    def test_resolve_push_base_auto_falls_back_to_origin_branch(self):
        original_run_command = push_guard.run_command

        def fake_run_command(args, *, cwd):
            if args[-1] == "@{upstream}":
                return subprocess.CompletedProcess(args, 128, "", "no upstream")
            if args[:4] == ["git", "rev-parse", "--verify", "--quiet"]:
                self.assertEqual(args[-1], "origin/codex/work")
                return subprocess.CompletedProcess(args, 0, "sha\n", "")
            self.fail(f"unexpected command: {args}")

        try:
            push_guard.run_command = fake_run_command
            base = push_guard.resolve_push_base(Path("."), "codex/work", "auto")
        finally:
            push_guard.run_command = original_run_command

        self.assertEqual(base, "origin/codex/work")

    def test_resolve_push_base_auto_returns_none_for_new_branch(self):
        original_run_command = push_guard.run_command

        def fake_run_command(args, *, cwd):
            return subprocess.CompletedProcess(args, 128, "", "missing")

        try:
            push_guard.run_command = fake_run_command
            base = push_guard.resolve_push_base(Path("."), "codex/new", "auto")
        finally:
            push_guard.run_command = original_run_command

        self.assertIsNone(base)

    def test_check_push_base_reports_ahead_and_behind_counts(self):
        original_run_command = push_guard.run_command

        def fake_run_command(args, *, cwd):
            if args[:4] == ["git", "rev-parse", "--verify", "--quiet"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[:3] == ["git", "log", "--left-right"]:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    "< abc1234 remote commit\n> def5678 local commit\n",
                    "",
                )
            self.fail(f"unexpected command: {args}")

        try:
            push_guard.run_command = fake_run_command
            errors, ahead_count, behind_count = push_guard.check_push_base(Path("."), "origin/work")
        finally:
            push_guard.run_command = original_run_command

        self.assertEqual(ahead_count, 1)
        self.assertEqual(behind_count, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("behind origin/work", errors[0])


if __name__ == "__main__":
    unittest.main()
