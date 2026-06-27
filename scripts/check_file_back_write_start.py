"""Check that a guarded file-back can start writing without re-importing.

Run this after check_file_back_preflight.py and immediately before the first
grasp write command. Unlike preflight, this script never imports Markdown into
the store; it only verifies that the preflight stamp, git-tracked projection,
and SQLite-authority projection checks are still clean.
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
    run_preflight_stamp_check,
    run_projection_check,
    run_semantic_log_projection_check,
    run_write_status,
)
from check_file_back_preflight import (
    DEFAULT_DIRTY_PATHS,
    DEFAULT_NO_JOURNAL_DIRTY_PATHS,
    check_dirty_paths,
    resolve_require_journal,
)


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
    expected_session_id: str = "",
) -> list[str]:
    errors: list[str] = []
    if require_preflight_stamp:
        errors.extend(
            run_preflight_stamp_check(
                repo,
                stamp_path=Path(preflight_stamp) if Path(preflight_stamp).is_absolute() else repo / preflight_stamp,
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
    parser.add_argument("--store", default=".grasp/file-back.sqlite")
    parser.add_argument("--project", default="grasp-wiki")
    parser.add_argument("--journal", default="wiki.grasp/events.jsonl")
    parser.add_argument("--output", default="wiki")
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
        "--skip-preflight-stamp-check",
        action="store_true",
        help="Skip the preflight stamp guard for legacy/ad hoc verification.",
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
        expected_session_id=args.session_id,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "file-back write-start ok: "
        f"store={args.store} project={args.project} output={args.output} "
        f"journal_mode={args.journal if require_journal else 'none'} "
        f"session={args.session_id if not args.skip_preflight_stamp_check else 'skipped'} "
        f"preflight_stamp={'skipped' if args.skip_preflight_stamp_check else args.preflight_stamp} "
        f"semantic_log={'skipped' if args.skip_semantic_log_check else 'ok'} "
        f"dirty_paths={','.join(paths)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
