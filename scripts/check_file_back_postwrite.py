"""Check that a grasp write-first file-back landed cleanly.

Run this after grasp write commands updated wiki/, before staging or committing
the projection. The default mode is no-journal and also checks the SQLite
events-derived semantic log projection; compatibility journal checks are
explicit opt-in.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_file_back_preflight import (
    parse_json_output,
    require_success,
    resolve_require_journal,
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
    require_session: bool = True,
    expected_session_id: str = "",
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
    if require_session:
        errors.extend(session_metadata_errors(status_json, expected_session_id=expected_session_id))
    if completed.returncode != 0 and not errors:
        errors.append(f"grasp write-status --strict failed with exit {completed.returncode}")
    return errors


def session_metadata_errors(result: dict[str, object], *, expected_session_id: str = "") -> list[str]:
    errors: list[str] = []
    expected = str(expected_session_id or "").strip()
    if not expected:
        errors.append(
            "file-back session id is required; set GRASP_SESSION_ID or pass --session-id "
            "(use --skip-session-check only for legacy/ad hoc verification)"
        )
    sqlite_last_event = result.get("sqlite_last_event")
    if not isinstance(sqlite_last_event, dict):
        errors.append("write-status sqlite_last_event is missing; run a grasp write before postwrite")
        return errors
    actual = str(sqlite_last_event.get("session_id") or "").strip()
    event_id = str(sqlite_last_event.get("event_id") or "")
    if not actual:
        errors.append(
            f"write-status sqlite_last_event {event_id!r} has empty session_id; "
            "write with --session-id or GRASP_SESSION_ID"
        )
    elif expected and actual != expected:
        errors.append(f"write-status sqlite_last_event session_id={actual!r}, expected {expected!r}")
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


def semantic_log_projection_errors(result: dict[str, object]) -> list[str]:
    errors = projection_policy_errors(result)
    if errors:
        return errors
    policy = result.get("projection_policy")
    if not isinstance(policy, dict):
        return ["missing projection_policy object"]
    overlays = policy.get("generated_overlays")
    if not isinstance(overlays, list):
        return ["projection_policy.generated_overlays must be a list"]
    if result.get("log_event_source") != "sqlite":
        errors.append(f"log_event_source={result.get('log_event_source')!r}, expected 'sqlite'")
    if "sqlite-events-log" not in overlays:
        errors.append("projection_policy.generated_overlays is missing 'sqlite-events-log'")
    regenerated_files = result.get("regenerated_files")
    if not isinstance(regenerated_files, list) or not regenerated_files:
        errors.append("regenerated_files must include the semantic log projection")
    return errors


def run_semantic_log_projection_check(repo: Path, *, store: str, project: str, output: str) -> list[str]:
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
            "--regenerate-log",
            "--check",
        ],
        cwd=repo,
    )
    projection_json, error = parse_json_output(completed.stdout, "export-markdown --regenerate-log")
    if projection_json is None:
        command_error = require_success(completed, "grasp export-markdown --regenerate-log --check")
        return [command_error or error or "export-markdown --regenerate-log returned no JSON"]
    errors = semantic_log_projection_errors(projection_json)
    if completed.returncode != 0 and not errors:
        errors.append(f"grasp export-markdown --regenerate-log --check failed with exit {completed.returncode}")
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
    semantic_log_check: bool,
    require_session: bool = True,
    expected_session_id: str = "",
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
            require_session=require_session,
            expected_session_id=expected_session_id,
        )
    )
    errors.extend(run_projection_check(repo, store=store, project=project, output=output))
    if semantic_log_check:
        errors.extend(run_semantic_log_projection_check(repo, store=store, project=project, output=output))
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
        help="Use write-status --no-journal and skip compatibility journal guards. This is the default.",
    )
    parser.add_argument(
        "--with-journal",
        action="store_true",
        help="Require the compatibility JSONL journal and run journal consistency guards.",
    )
    parser.add_argument("--output", default="wiki")
    parser.add_argument("--skip-lint", action="store_true", help="Skip scripts/lint_wiki.py.")
    parser.add_argument("--skip-diff-check", action="store_true", help="Skip git diff --check.")
    parser.add_argument(
        "--skip-semantic-log-check",
        action="store_true",
        help="Skip export-markdown --regenerate-log --check for the SQLite events-derived log projection.",
    )
    parser.add_argument(
        "--session-id",
        default=os.environ.get("GRASP_SESSION_ID", ""),
        help="Expected session marker on the latest SQLite event. Defaults to $GRASP_SESSION_ID.",
    )
    parser.add_argument(
        "--skip-session-check",
        action="store_true",
        help="Skip the latest-event session marker guard for legacy/ad hoc verification.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    try:
        require_journal = resolve_require_journal(no_journal=args.no_journal, with_journal=args.with_journal)
    except ValueError as error:
        parser.error(str(error))
    errors = run_postwrite_checks(
        repo,
        store=args.store,
        project=args.project,
        journal=args.journal if require_journal else None,
        output=args.output,
        require_journal=require_journal,
        lint=not args.skip_lint,
        diff_check=not args.skip_diff_check,
        semantic_log_check=not args.skip_semantic_log_check,
        require_session=not args.skip_session_check,
        expected_session_id=args.session_id,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "file-back postwrite ok: "
        f"store={args.store} project={args.project} output={args.output} "
        f"journal_mode={args.journal if require_journal else 'none'} "
        f"semantic_log={'skipped' if args.skip_semantic_log_check else 'ok'} "
        f"session={'skipped' if args.skip_session_check else args.session_id} "
        f"lint={'skipped' if args.skip_lint else 'ok'} "
        f"diff_check={'skipped' if args.skip_diff_check else 'ok'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
