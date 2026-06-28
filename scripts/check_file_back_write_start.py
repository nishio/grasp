"""Check that a guarded file-back can start writing without re-importing.

Run this after check_file_back_preflight.py and immediately before the first
grasp write command. Unlike preflight, this script never imports Markdown into
the store; it only verifies that the preflight stamp, git-tracked projection,
SQLite event stream, and SQLite-authority projection checks are still clean.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_file_back_postwrite import (
    DEFAULT_PREFLIGHT_STAMP,
    event_sequence,
    load_preflight_stamp,
    run_preflight_stamp_check,
    run_projection_check,
    run_semantic_log_projection_check,
    run_write_status,
)
from check_file_back_preflight import (
    DEFAULT_DIRTY_PATHS,
    DEFAULT_FILE_BACK_LOCK,
    DEFAULT_FILE_BACK_OUTPUT,
    DEFAULT_FILE_BACK_STORE,
    DEFAULT_NO_JOURNAL_DIRTY_PATHS,
    check_dirty_paths,
    file_back_store_output_pair_errors,
    latest_event_sequence,
    project_events,
    print_errors_and_recovery,
    run_file_back_lock_check,
    resolve_repo_path,
    resolve_require_journal,
)


def run_preflight_event_sequence_unchanged_check(
    repo: Path,
    *,
    stamp_path: Path,
    store: str,
    project: str,
) -> list[str]:
    stamp, error = load_preflight_stamp(stamp_path)
    if stamp is None:
        return [error or "preflight stamp returned no JSON"]
    if "sqlite_event_sequence" not in stamp:
        return ["preflight stamp sqlite_event_sequence is missing"]
    baseline = event_sequence(stamp.get("sqlite_event_sequence"))
    if stamp.get("sqlite_event_sequence") is not None and baseline is None:
        return [f"preflight stamp sqlite_event_sequence={stamp.get('sqlite_event_sequence')!r}, expected integer or null"]
    try:
        current = latest_event_sequence(project_events(str(resolve_repo_path(repo, store)), project))
    except Exception as error:
        return [f"could not inspect SQLite events before file-back write-start: {error}"]
    if current == baseline:
        return []
    return [
        "SQLite events changed after preflight before write-start; "
        "rerun check_file_back_preflight.py before writing "
        f"(preflight_event_sequence={baseline}, current_event_sequence={current})"
    ]


def run_write_start_checks(
    repo: Path,
    *,
    store: str,
    project: str,
    journal: str | None,
    output: str,
    require_journal: bool = True,
    dirty_paths: tuple[str, ...] = DEFAULT_NO_JOURNAL_DIRTY_PATHS,
    semantic_log_check: bool = True,
    require_preflight_stamp: bool = True,
    preflight_stamp: str = DEFAULT_PREFLIGHT_STAMP,
    require_file_back_lock: bool = True,
    file_back_lock: str = DEFAULT_FILE_BACK_LOCK,
    expected_session_id: str = "",
) -> list[str]:
    errors: list[str] = []
    errors.extend(file_back_store_output_pair_errors(repo, store=store, output=output))
    if errors:
        return errors
    if require_preflight_stamp:
        stamp_path = Path(preflight_stamp) if Path(preflight_stamp).is_absolute() else repo / preflight_stamp
        stamp_errors = run_preflight_stamp_check(
            repo,
            stamp_path=stamp_path,
            expected_session_id=expected_session_id,
            store=store,
            project=project,
            output=output,
        )
        errors.extend(stamp_errors)
        if not stamp_errors:
            errors.extend(
                run_preflight_event_sequence_unchanged_check(
                    repo,
                    stamp_path=stamp_path,
                    store=store,
                    project=project,
                )
            )
    if require_file_back_lock:
        errors.extend(
            run_file_back_lock_check(
                resolve_repo_path(repo, file_back_lock),
                expected_session_id=expected_session_id,
                store=store,
                project=project,
                output=output,
            )
        )
    errors.extend(check_dirty_paths(repo, dirty_paths))
    errors.extend(
        run_write_status(
            repo,
            store=store,
            project=project,
            journal=journal,
            output=output,
            require_journal=require_journal,
            require_session=False,
            expected_session_id="",
        )
    )
    errors.extend(run_projection_check(repo, store=store, project=project, output=output))
    if semantic_log_check:
        errors.extend(run_semantic_log_projection_check(repo, store=store, project=project, output=output))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check guarded grasp file-back write-start conditions.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--store", default=DEFAULT_FILE_BACK_STORE)
    parser.add_argument("--project", default="grasp-wiki")
    parser.add_argument("--journal", default="wiki.grasp/events.jsonl")
    parser.add_argument("--output", default=DEFAULT_FILE_BACK_OUTPUT)
    parser.add_argument(
        "--session-id",
        default=os.environ.get("GRASP_SESSION_ID", ""),
        help="Expected session marker from preflight. Defaults to $GRASP_SESSION_ID.",
    )
    parser.add_argument(
        "--preflight-stamp",
        default=DEFAULT_PREFLIGHT_STAMP,
        help="Gitignored JSON stamp created by preflight.",
    )
    parser.add_argument(
        "--file-back-lock",
        default=DEFAULT_FILE_BACK_LOCK,
        help="Gitignored lock created by preflight and released by postwrite.",
    )
    parser.add_argument(
        "--skip-preflight-stamp-check",
        action="store_true",
        help="Skip the preflight stamp guard for legacy/ad hoc verification.",
    )
    parser.add_argument(
        "--skip-file-back-lock-check",
        action="store_true",
        help="Skip the file-back lock guard for legacy/ad hoc verification.",
    )
    parser.add_argument(
        "--skip-semantic-log-check",
        action="store_true",
        help="Skip export-markdown --regenerate-log --check for the SQLite events-derived log projection.",
    )
    parser.add_argument(
        "--dirty-path",
        action="append",
        dest="dirty_paths",
        help="Path that must still be clean before the first write. Defaults to wiki and the retired repo JSONL journal path.",
    )
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
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    try:
        require_journal = resolve_require_journal(no_journal=args.no_journal, with_journal=args.with_journal)
    except ValueError as error:
        parser.error(str(error))
    paths = tuple(args.dirty_paths) if args.dirty_paths else (
        DEFAULT_DIRTY_PATHS if require_journal else DEFAULT_NO_JOURNAL_DIRTY_PATHS
    )
    errors = run_write_start_checks(
        repo,
        store=args.store,
        project=args.project,
        journal=args.journal if require_journal else None,
        output=args.output,
        require_journal=require_journal,
        dirty_paths=paths,
        semantic_log_check=not args.skip_semantic_log_check,
        require_preflight_stamp=not args.skip_preflight_stamp_check,
        preflight_stamp=args.preflight_stamp,
        require_file_back_lock=not args.skip_file_back_lock_check,
        file_back_lock=args.file_back_lock,
        expected_session_id=args.session_id,
    )
    if errors:
        print_errors_and_recovery(errors, store=args.store, project=args.project, output=args.output)
        return 1

    session_status = (
        "skipped" if args.skip_preflight_stamp_check and args.skip_file_back_lock_check else args.session_id
    )
    print(
        "file-back write-start ok: "
        f"store={args.store} project={args.project} output={args.output} "
        f"journal_mode={args.journal if require_journal else 'none'} "
        f"session={session_status} "
        f"preflight_stamp={'skipped' if args.skip_preflight_stamp_check else args.preflight_stamp} "
        f"lock={'skipped' if args.skip_file_back_lock_check else args.file_back_lock} "
        f"event_sequence={'skipped' if args.skip_preflight_stamp_check else 'unchanged'} "
        f"semantic_log={'skipped' if args.skip_semantic_log_check else 'ok'} "
        f"dirty_paths={','.join(paths)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
