"""Check that a grasp write-first file-back landed cleanly.

Run this after grasp write commands updated wiki/ and wiki.grasp/events.jsonl,
before staging or committing the projection.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_file_back_preflight import (
    parse_json_output,
    require_success,
    run_command,
    write_status_command,
    write_status_errors,
)
from check_projection_policy import projection_policy_errors


def run_write_status(
    repo: Path,
    *,
    store: str,
    project: str,
    journal: str | None,
    output: str,
    require_journal: bool = True,
) -> list[str]:
    completed = run_command(
        write_status_command(
            store=store,
            project=project,
            journal=journal,
            output=output,
            require_journal=require_journal,
        ),
        cwd=repo,
    )
    status_json, error = parse_json_output(completed.stdout, "write-status")
    if status_json is None:
        command_error = require_success(completed, "grasp write-status --strict")
        return [command_error or error or "write-status returned no JSON"]
    errors = write_status_errors(status_json, require_journal=require_journal)
    if completed.returncode != 0 and not errors:
        errors.append(f"grasp write-status --strict failed with exit {completed.returncode}")
    return errors


def run_projection_check(repo: Path, *, store: str, project: str, output: str) -> list[str]:
    completed = run_command(
        [
            sys.executable,
            "-m",
            "grasp",
            "--json",
            "--store",
            store,
            "--project",
            project,
            "export-markdown",
            "--output",
            output,
            "--check",
        ],
        cwd=repo,
    )
    projection_json, error = parse_json_output(completed.stdout, "export-markdown")
    if projection_json is None:
        command_error = require_success(completed, "grasp export-markdown --check")
        return [command_error or error or "export-markdown returned no JSON"]
    errors = projection_policy_errors(projection_json)
    if completed.returncode != 0 and not errors:
        errors.append(f"grasp export-markdown --check failed with exit {completed.returncode}")
    return errors


def run_optional_command(repo: Path, args: list[str], label: str) -> list[str]:
    completed = run_command(args, cwd=repo)
    error = require_success(completed, label)
    return [error] if error else []


def run_postwrite_checks(
    repo: Path,
    *,
    store: str,
    project: str,
    journal: str | None,
    output: str,
    require_journal: bool = True,
    lint: bool,
    diff_check: bool,
) -> list[str]:
    errors: list[str] = []
    errors.extend(
        run_write_status(
            repo,
            store=store,
            project=project,
            journal=journal,
            output=output,
            require_journal=require_journal,
        )
    )
    errors.extend(run_projection_check(repo, store=store, project=project, output=output))
    if lint:
        errors.extend(run_optional_command(repo, [sys.executable, "scripts/lint_wiki.py"], "wiki lint"))
    if diff_check:
        errors.extend(run_optional_command(repo, ["git", "diff", "--check"], "git diff --check"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check guarded grasp file-back post-write conditions.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--store", default=".grasp/file-back.sqlite")
    parser.add_argument("--project", default="grasp-wiki")
    parser.add_argument("--journal", default="wiki.grasp/events.jsonl")
    parser.add_argument(
        "--no-journal",
        action="store_true",
        help="Use write-status --no-journal and skip compatibility journal guards.",
    )
    parser.add_argument("--output", default="wiki")
    parser.add_argument("--skip-lint", action="store_true", help="Skip scripts/lint_wiki.py.")
    parser.add_argument("--skip-diff-check", action="store_true", help="Skip git diff --check.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    errors = run_postwrite_checks(
        repo,
        store=args.store,
        project=args.project,
        journal=None if args.no_journal else args.journal,
        output=args.output,
        require_journal=not args.no_journal,
        lint=not args.skip_lint,
        diff_check=not args.skip_diff_check,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "file-back postwrite ok: "
        f"store={args.store} project={args.project} output={args.output} "
        f"journal_mode={'none' if args.no_journal else args.journal} "
        f"lint={'skipped' if args.skip_lint else 'ok'} "
        f"diff_check={'skipped' if args.skip_diff_check else 'ok'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
