"""Check that a grasp write-first file-back landed cleanly.

Run this after grasp write commands updated wiki/, before staging or committing
the projection. The default mode is no-journal and also checks the SQLite
events-derived semantic log projection; compatibility journal checks are
explicit opt-in.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_file_back_preflight import (
    DEFAULT_FILE_BACK_OUTPUT,
    DEFAULT_FILE_BACK_STORE,
    DEFAULT_PREFLIGHT_STAMP,
    PREFLIGHT_STAMP_KIND,
    PREFLIGHT_STAMP_SCHEMA_VERSION,
    file_back_store_output_pair_errors,
    git_ref_oid,
    parse_json_output,
    require_success,
    resolve_repo_path,
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


def load_preflight_stamp(path: Path) -> tuple[dict[str, object] | None, str | None]:
    if not path.exists():
        return None, f"preflight stamp is missing: {path}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return None, f"preflight stamp {path} is not valid JSON: {error}"
    except OSError as error:
        return None, f"preflight stamp {path} could not be read: {error}"
    if not isinstance(value, dict):
        return None, f"preflight stamp {path} returned {type(value).__name__}, expected object"
    return value, None


def preflight_stamp_errors(
    stamp: dict[str, object],
    *,
    expected_session_id: str,
    current_head: str,
    current_base_oid: str | None,
    store: str,
    project: str,
    output: str,
) -> list[str]:
    errors: list[str] = []
    if stamp.get("schema_version") != PREFLIGHT_STAMP_SCHEMA_VERSION:
        errors.append(
            "preflight stamp schema_version="
            f"{stamp.get('schema_version')!r}, expected {PREFLIGHT_STAMP_SCHEMA_VERSION!r}"
        )
    if stamp.get("kind") != PREFLIGHT_STAMP_KIND:
        errors.append(f"preflight stamp kind={stamp.get('kind')!r}, expected {PREFLIGHT_STAMP_KIND!r}")
    expected = str(expected_session_id or "").strip()
    stamped_session = str(stamp.get("session_id") or "").strip()
    if not expected:
        errors.append("preflight stamp check requires GRASP_SESSION_ID or --session-id")
    elif stamped_session != expected:
        errors.append(f"preflight stamp session_id={stamped_session!r}, expected {expected!r}")
    stamped_head = str(stamp.get("head") or "").strip()
    if not stamped_head:
        errors.append("preflight stamp head is missing")
    elif stamped_head != current_head:
        errors.append(f"current HEAD={current_head!r} differs from preflight stamp head={stamped_head!r}")
    base = stamp.get("base")
    if base is None:
        errors.append("preflight stamp base is missing")
    elif not isinstance(base, str):
        errors.append(f"preflight stamp base={base!r}, expected string")
    elif base != "skipped":
        stamped_base_oid = str(stamp.get("base_oid") or "").strip()
        if not stamped_base_oid:
            errors.append(f"preflight stamp base_oid is missing for base={base!r}")
        elif current_base_oid != stamped_base_oid:
            errors.append(
                f"current base {base} oid={current_base_oid!r} differs from "
                f"preflight stamp base_oid={stamped_base_oid!r}"
            )
    for key, expected_value in (("store", store), ("project", project), ("output", output)):
        actual_value = str(stamp.get(key) or "")
        if actual_value != expected_value:
            errors.append(f"preflight stamp {key}={actual_value!r}, expected {expected_value!r}")
    return errors


def run_preflight_stamp_check(
    repo: Path,
    *,
    stamp_path: Path,
    expected_session_id: str,
    store: str,
    project: str,
    output: str,
) -> list[str]:
    stamp, error = load_preflight_stamp(stamp_path)
    if stamp is None:
        return [error or "preflight stamp returned no JSON"]
    current_head, error = git_ref_oid(repo, "HEAD")
    if error:
        return [error]
    base = stamp.get("base")
    current_base_oid = None
    if isinstance(base, str) and base and base != "skipped":
        current_base_oid, error = git_ref_oid(repo, base)
        if error:
            return [error]
    return preflight_stamp_errors(
        stamp,
        expected_session_id=expected_session_id,
        current_head=current_head or "",
        current_base_oid=current_base_oid,
        store=store,
        project=project,
        output=output,
    )


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
    require_preflight_stamp: bool = True,
    preflight_stamp: str = DEFAULT_PREFLIGHT_STAMP,
) -> list[str]:
    errors: list[str] = []
    errors.extend(file_back_store_output_pair_errors(repo, store=store, output=output))
    if errors:
        return errors
    if require_preflight_stamp:
        errors.extend(
            run_preflight_stamp_check(
                repo,
                stamp_path=resolve_repo_path(repo, preflight_stamp),
                expected_session_id=expected_session_id,
                store=store,
                project=project,
                output=output,
            )
        )
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
    parser.add_argument("--store", default=DEFAULT_FILE_BACK_STORE)
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
    parser.add_argument("--output", default=DEFAULT_FILE_BACK_OUTPUT)
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
    parser.add_argument(
        "--preflight-stamp",
        default=DEFAULT_PREFLIGHT_STAMP,
        help="Gitignored JSON stamp created by preflight.",
    )
    parser.add_argument(
        "--skip-preflight-stamp-check",
        action="store_true",
        help="Skip the preflight stamp guard for legacy/ad hoc verification.",
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
        require_preflight_stamp=not args.skip_preflight_stamp_check,
        preflight_stamp=args.preflight_stamp,
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
        f"preflight_stamp={'skipped' if args.skip_preflight_stamp_check else args.preflight_stamp} "
        f"lint={'skipped' if args.skip_lint else 'ok'} "
        f"diff_check={'skipped' if args.skip_diff_check else 'ok'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
