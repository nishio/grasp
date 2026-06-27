"""Check that grasp write-first file-back can start safely.

The check is intentionally repo-facing: run it after fetching the upstream base
and before any grasp write command touches wiki/. The default mode is
no-journal and also guards that the retired repo JSONL journal path stays clean.
Compatibility journal checks are explicit opt-in for legacy/ad hoc audits.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from check_projection_policy import projection_policy_errors
from grasp.sqlite_store import SQLiteStore


DEFAULT_DIRTY_PATHS = ("wiki", "wiki.grasp/events.jsonl")
DEFAULT_NO_JOURNAL_DIRTY_PATHS = ("wiki", "wiki.grasp/events.jsonl")
DEFAULT_BASE = "auto"
FALLBACK_BASE = "origin/main"
DEFAULT_PREFLIGHT_STAMP = ".grasp/file-back-preflight.json"
PREFLIGHT_STAMP_KIND = "grasp_file_back_preflight"
PREFLIGHT_STAMP_SCHEMA_VERSION = 1


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def require_success(completed: subprocess.CompletedProcess[str], label: str) -> str | None:
    if completed.returncode == 0:
        return None
    detail = (completed.stderr or completed.stdout).strip()
    return f"{label} failed with exit {completed.returncode}: {detail}"


def dirty_path_errors(status_output: str) -> list[str]:
    lines = [line for line in status_output.splitlines() if line.strip()]
    if not lines:
        return []
    return ["dirty file-back paths before file-back:\n" + "\n".join(lines)]


def base_divergence_errors(log_output: str, base: str) -> list[str]:
    lines = [line for line in log_output.splitlines() if line.strip()]
    if not lines:
        return []
    return [f"branch differs from {base}; reconcile before file-back:\n" + "\n".join(lines)]


def resolve_git_base(repo: Path, requested_base: str) -> str:
    if requested_base != DEFAULT_BASE:
        return requested_base
    upstream = run_command(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=repo,
    )
    if upstream.returncode == 0:
        upstream_name = upstream.stdout.strip()
        if upstream_name:
            return upstream_name
    return FALLBACK_BASE


def resolve_repo_path(repo: Path, path: str) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return repo / resolved


def git_ref_oid(repo: Path, ref: str) -> tuple[str | None, str | None]:
    completed = run_command(["git", "rev-parse", "--verify", ref], cwd=repo)
    error = require_success(completed, f"git rev-parse {ref}")
    if error:
        return None, error
    return completed.stdout.strip(), None


def preflight_stamp_payload(
    *,
    session_id: str,
    head: str,
    base: str | None,
    base_oid: str | None,
    store: str,
    project: str,
    output: str,
    journal_mode: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": PREFLIGHT_STAMP_SCHEMA_VERSION,
        "kind": PREFLIGHT_STAMP_KIND,
        "created_at": created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session_id": session_id,
        "head": head,
        "base": base or "skipped",
        "base_oid": base_oid,
        "store": store,
        "project": project,
        "output": output,
        "journal_mode": journal_mode,
    }


def preflight_stamp_from_repo(
    repo: Path,
    *,
    session_id: str,
    base: str | None,
    store: str,
    project: str,
    output: str,
    journal_mode: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    head, error = git_ref_oid(repo, "HEAD")
    if error:
        return None, [error]
    base_oid = None
    if base:
        base_oid, error = git_ref_oid(repo, base)
        if error:
            return None, [error]
    return (
        preflight_stamp_payload(
            session_id=session_id,
            head=head or "",
            base=base,
            base_oid=base_oid,
            store=store,
            project=project,
            output=output,
            journal_mode=journal_mode,
        ),
        [],
    )


def write_preflight_stamp(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_status_errors(result: dict[str, Any], *, require_journal: bool = True) -> list[str]:
    errors: list[str] = []
    projection = result.get("projection")
    projection_ok = result.get("projection_ok")
    if projection_ok is None and isinstance(projection, dict):
        projection_ok = projection.get("ok")
    if result.get("strict_ok") is not True:
        errors.append(f"write-status strict_ok={result.get('strict_ok')!r}, expected True")
    if projection_ok is not True:
        errors.append(f"write-status projection ok={projection_ok!r}, expected True")
    if result.get("semantic_log_stale") is True:
        errors.append("write-status semantic_log_stale is true")
    if result.get("semantic_log_error"):
        errors.append(f"write-status semantic_log_error={result.get('semantic_log_error')!r}")
    semantic_policy_errors = result.get("semantic_log_policy_errors")
    if semantic_policy_errors:
        errors.append(f"write-status semantic_log_policy_errors={semantic_policy_errors!r}")
    if require_journal:
        if result.get("journal_exists") is not True:
            errors.append("write-status journal_exists is not true")
        if result.get("event_streams_match") is not True:
            errors.append("write-status event_streams_match is not true")
        if result.get("journal_log_stale") is True:
            errors.append("write-status journal_log_stale is true")
    return errors


def session_uniqueness_errors(
    events: list[dict[str, Any]],
    *,
    expected_session_id: str | None,
    skip_session_uniqueness_check: bool = False,
) -> list[str]:
    if skip_session_uniqueness_check:
        return []
    session_id = str(expected_session_id or "").strip()
    if not session_id:
        return ["GRASP_SESSION_ID or --session-id is required before file-back"]
    matching_events = [
        event
        for event in events
        if str(event.get("session_id") or "") == session_id
    ]
    if not matching_events:
        return []
    first = matching_events[0]
    last = matching_events[-1]
    return [
        "session_id already exists before file-back; choose a unique GRASP_SESSION_ID: "
        f"{session_id} ({len(matching_events)} events, "
        f"first_sequence={first.get('event_sequence')}, last_sequence={last.get('event_sequence')})"
    ]


def parse_json_output(output: str, label: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        return None, f"{label} did not return valid JSON: {error}"
    if not isinstance(value, dict):
        return None, f"{label} returned {type(value).__name__}, expected object"
    return value, None


def check_git_base(repo: Path, base: str) -> list[str]:
    verify = run_command(["git", "rev-parse", "--verify", "--quiet", base], cwd=repo)
    error = require_success(verify, f"git rev-parse {base}")
    if error:
        return [error]
    divergence = run_command(["git", "log", "--left-right", "--cherry-pick", "--oneline", f"{base}...HEAD"], cwd=repo)
    error = require_success(divergence, f"git log {base}...HEAD")
    if error:
        return [error]
    return base_divergence_errors(divergence.stdout, base)


def check_dirty_paths(repo: Path, paths: tuple[str, ...]) -> list[str]:
    status = run_command(["git", "status", "--porcelain=v1", "--", *paths], cwd=repo)
    error = require_success(status, "git status")
    if error:
        return [error]
    return dirty_path_errors(status.stdout)


def project_events(store: str, project: str) -> list[dict[str, Any]]:
    sqlite_store = SQLiteStore(store, project=project, for_write=False)
    try:
        return sqlite_store.events(project=project, limit=None)
    finally:
        sqlite_store.close()


def write_status_command(
    *,
    store: str,
    project: str,
    journal: str | None,
    output: str,
    require_journal: bool,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "grasp",
        "--store",
        store,
        "--project",
        project,
        "--json",
        "write-status",
        "--output",
        output,
    ]
    if require_journal:
        if not journal:
            raise ValueError("journal path is required when require_journal=True")
        command.extend(["--journal", journal])
    else:
        command.append("--no-journal")
    command.append("--strict")
    return command


def run_grasp_preflight(
    repo: Path,
    *,
    store: str,
    project: str,
    journal: str | None,
    output: str,
    require_journal: bool = True,
    expected_session_id: str | None = None,
    skip_session_uniqueness_check: bool = False,
) -> list[str]:
    errors: list[str] = []

    import_result = run_command(
        [sys.executable, "-m", "grasp", "--store", store, "import", "--markdown", output, "--project", project],
        cwd=repo,
    )
    error = require_success(import_result, "grasp import --markdown")
    if error:
        return [error]

    write_status = run_command(
        write_status_command(
            store=store,
            project=project,
            journal=journal,
            output=output,
            require_journal=require_journal,
        ),
        cwd=repo,
    )
    status_json, error = parse_json_output(write_status.stdout, "write-status")
    if status_json is None:
        command_error = require_success(write_status, "grasp write-status --strict")
        return [command_error or error or "write-status returned no JSON"]
    errors.extend(write_status_errors(status_json, require_journal=require_journal))
    if write_status.returncode != 0 and not errors:
        errors.append(f"grasp write-status --strict failed with exit {write_status.returncode}")
    if errors:
        return errors

    errors.extend(
        session_uniqueness_errors(
            project_events(store, project),
            expected_session_id=expected_session_id,
            skip_session_uniqueness_check=skip_session_uniqueness_check,
        )
    )
    if errors:
        return errors

    projection = run_command(
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
    projection_json, error = parse_json_output(projection.stdout, "export-markdown")
    if projection_json is None:
        command_error = require_success(projection, "grasp export-markdown --check")
        return [command_error or error or "export-markdown returned no JSON"]
    errors.extend(projection_policy_errors(projection_json))
    if projection.returncode != 0 and not errors:
        errors.append(f"grasp export-markdown --check failed with exit {projection.returncode}")
    if errors:
        return errors
    return errors


def resolve_require_journal(*, no_journal: bool, with_journal: bool) -> bool:
    if no_journal and with_journal:
        raise ValueError("--no-journal and --with-journal are mutually exclusive")
    return with_journal


def main() -> int:
    parser = argparse.ArgumentParser(description="Check guarded grasp file-back preflight conditions.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help="Fetched git base to compare with HEAD. 'auto' prefers the current upstream branch, then origin/main.",
    )
    parser.add_argument("--skip-base-check", action="store_true", help="Skip the base divergence check.")
    parser.add_argument("--store", default=".grasp/file-back.sqlite")
    parser.add_argument("--project", default="grasp-wiki")
    parser.add_argument("--journal", default="wiki.grasp/events.jsonl")
    parser.add_argument("--session-id", default=os.environ.get("GRASP_SESSION_ID", ""), help="Unique session/work-unit id expected for the upcoming file-back. Defaults to $GRASP_SESSION_ID.")
    parser.add_argument(
        "--skip-session-uniqueness-check",
        action="store_true",
        help="Skip the unused-session-id guard for legacy/ad hoc verification.",
    )
    parser.add_argument(
        "--preflight-stamp",
        default=DEFAULT_PREFLIGHT_STAMP,
        help="Gitignored JSON stamp written after a clean preflight and checked by postwrite.",
    )
    parser.add_argument(
        "--skip-preflight-stamp",
        action="store_true",
        help="Skip writing the preflight stamp for legacy/ad hoc verification.",
    )
    parser.add_argument(
        "--no-journal",
        action="store_true",
        help="Use write-status --no-journal and do not require the compatibility journal to be clean. This is the default.",
    )
    parser.add_argument(
        "--with-journal",
        action="store_true",
        help="Require the compatibility JSONL journal and run journal consistency guards.",
    )
    parser.add_argument("--output", default="wiki")
    parser.add_argument(
        "--dirty-path",
        action="append",
        dest="dirty_paths",
        help="Path that must be clean before file-back. Defaults to wiki and the retired repo JSONL journal path.",
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
    errors: list[str] = []
    resolved_base = args.base
    if not args.skip_base_check:
        resolved_base = resolve_git_base(repo, args.base)
        errors.extend(check_git_base(repo, resolved_base))
    errors.extend(check_dirty_paths(repo, paths))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    errors.extend(
        run_grasp_preflight(
            repo,
            store=args.store,
            project=args.project,
            journal=args.journal if require_journal else None,
            output=args.output,
            require_journal=require_journal,
            expected_session_id=args.session_id,
            skip_session_uniqueness_check=args.skip_session_uniqueness_check,
        )
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    stamp_written = "skipped"
    if not args.skip_preflight_stamp:
        if not args.skip_base_check:
            errors.extend(check_git_base(repo, resolved_base))
        if not errors:
            payload, stamp_errors = preflight_stamp_from_repo(
                repo,
                session_id=args.session_id,
                base=None if args.skip_base_check else resolved_base,
                store=args.store,
                project=args.project,
                output=args.output,
                journal_mode=args.journal if require_journal else "none",
            )
            errors.extend(stamp_errors)
            if payload is not None and not errors:
                stamp_path = resolve_repo_path(repo, args.preflight_stamp)
                try:
                    write_preflight_stamp(stamp_path, payload)
                except OSError as error:
                    errors.append(f"write preflight stamp {stamp_path} failed: {error}")
                else:
                    stamp_written = str(stamp_path.relative_to(repo) if stamp_path.is_relative_to(repo) else stamp_path)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1

    print(
        "file-back preflight ok: "
        f"base={resolved_base if not args.skip_base_check else 'skipped'} "
        f"journal_mode={args.journal if require_journal else 'none'} "
        f"session={'skipped' if args.skip_session_uniqueness_check else args.session_id} "
        f"stamp={stamp_written} "
        f"dirty_paths={','.join(paths)} "
        f"store={args.store} project={args.project} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
