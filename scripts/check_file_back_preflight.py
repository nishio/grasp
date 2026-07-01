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
import sqlite3
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
PROTECTED_BRANCHES = ("main", "master")
DEFAULT_FILE_BACK_STORE = ".grasp/file-back.sqlite"
DEFAULT_FILE_BACK_OUTPUT = "wiki"
DEFAULT_FILE_BACK_BOOTSTRAP_JOURNAL = ".grasp/file-back-adopt.jsonl"
DEFAULT_FILE_BACK_BOOTSTRAP_ACTOR = "file-back-preflight"
DEFAULT_FILE_BACK_BOOTSTRAP_SESSION_ID = "bootstrap-file-back-store"
DEFAULT_PREFLIGHT_STAMP = ".grasp/file-back-preflight.json"
DEFAULT_FILE_BACK_LOCK = ".grasp/file-back.lock.json"
PREFLIGHT_STAMP_KIND = "grasp_file_back_preflight"
PREFLIGHT_STAMP_SCHEMA_VERSION = 2
FILE_BACK_LOCK_KIND = "grasp_file_back_lock"
FILE_BACK_LOCK_SCHEMA_VERSION = 1


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


def recovery_ladder_hints(
    errors: list[str],
    *,
    store: str,
    project: str,
    output: str,
) -> list[str]:
    if not errors:
        return []
    joined = "\n".join(errors)
    hints = [
        "recovery ladder:",
        f"- inspect recent ownership: python3 -m grasp --store {store} --project {project} activity --limit 20",
        f"- inspect page claims: python3 -m grasp --store {store} --project {project} claims --include-expired",
    ]
    if "dirty file-back paths" in joined:
        hints.append(
            "- dirty projection/worktree: do not continue this file-back in place; "
            "fold into the active owner branch, or use an isolated worktree/direct-patch PR and record pending reconcile."
        )
    if (
        "branch differs from" in joined
        or "current HEAD=" in joined
        or "differs from preflight stamp head" in joined
    ):
        hints.append(
            "- branch/HEAD moved: fetch or merge the active owner work, discard the stale preflight stamp, and rerun preflight."
        )
    if "semantic_log_stale" in joined or "semantic log" in joined:
        hints.append(
            "- semantic log drift: normal write-first is not authoritative until the store/projection are reconciled; "
            "either reconcile once on a clean owner worktree or use direct-patch fallback with an explicit pending-reconcile note."
        )
    if "SQLite events changed after preflight" in joined:
        hints.append(
            "- store advanced after preflight: rerun preflight and use activity/session_id to decide whether to fold into that work unit or wait."
        )
    if "mixed file-back store/output pair" in joined:
        hints.append(
            "- store/output pair mismatch: use .grasp/file-back.sqlite with wiki, or use a temporary store together with a temporary output."
        )
    if "session_id already exists" in joined:
        hints.append(
            "- reused session_id: choose a fresh GRASP_SESSION_ID. "
            "The only normal prior same-session event before preflight is an active page_claim from claim-page."
        )
    if "another file-back lock is active" in joined or "active file-back lock" in joined:
        hints.append(
            "- active lock: wait for the owner to finish. If the owner is unreachable but its writes are already in the store, "
            "rerun postwrite with the lock owner's GRASP_SESSION_ID so the normal session-window checks release the lock; "
            "remove .grasp/file-back.lock.json only after confirming it is stale."
        )
    if len(hints) == 2:
        hints.append("- rerun the relevant guard after choosing a recovery path; do not bypass silently.")
    return hints


def print_errors_and_recovery(
    errors: list[str],
    *,
    store: str,
    project: str,
    output: str,
) -> None:
    for error in errors:
        print(error, file=sys.stderr)
    for hint in recovery_ladder_hints(errors, store=store, project=project, output=output):
        print(hint, file=sys.stderr)


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
    branch = current_branch_name(repo)
    if branch:
        remote_branch = f"origin/{branch}"
        if git_ref_exists(repo, remote_branch):
            return remote_branch
        if branch not in PROTECTED_BRANCHES:
            return "HEAD"
    return FALLBACK_BASE


def current_branch_name(repo: Path) -> str | None:
    current = run_command(["git", "branch", "--show-current"], cwd=repo)
    if current.returncode != 0:
        return None
    branch = current.stdout.strip()
    return branch or None


def git_ref_exists(repo: Path, ref: str) -> bool:
    return run_command(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo).returncode == 0


def resolve_repo_path(repo: Path, path: str) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return repo / resolved


def resolved_repo_path(repo: Path, path: str) -> Path:
    return resolve_repo_path(repo, path).resolve(strict=False)


def file_back_store_output_pair_errors(
    repo: Path,
    *,
    store: str,
    output: str,
) -> list[str]:
    default_store = resolved_repo_path(repo, DEFAULT_FILE_BACK_STORE)
    default_output = resolved_repo_path(repo, DEFAULT_FILE_BACK_OUTPUT)
    store_path = resolved_repo_path(repo, store)
    output_path = resolved_repo_path(repo, output)
    store_is_default = store_path == default_store
    output_is_default = output_path == default_output
    if store_is_default == output_is_default:
        return []
    return [
        "mixed file-back store/output pair: "
        f"store={store!r} resolves_to={store_path}, output={output!r} resolves_to={output_path}. "
        f"Use the repo dogfood pair store={DEFAULT_FILE_BACK_STORE!r} with output={DEFAULT_FILE_BACK_OUTPUT!r}, "
        "or use a temporary store together with a temporary output. "
        "Do not run a temporary output against the repo file-back store."
    ]


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
    sqlite_event_sequence: int | None,
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
        "sqlite_event_sequence": sqlite_event_sequence,
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
    sqlite_event_sequence: int | None,
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
            sqlite_event_sequence=sqlite_event_sequence,
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


def file_back_lock_payload(
    *,
    session_id: str,
    store: str,
    project: str,
    output: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": FILE_BACK_LOCK_SCHEMA_VERSION,
        "kind": FILE_BACK_LOCK_KIND,
        "created_at": created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session_id": session_id,
        "store": store,
        "project": project,
        "output": output,
    }


def load_file_back_lock(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"file-back lock is missing: {path}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return None, f"file-back lock {path} is not valid JSON: {error}"
    except OSError as error:
        return None, f"file-back lock {path} could not be read: {error}"
    if not isinstance(value, dict):
        return None, f"file-back lock {path} returned {type(value).__name__}, expected object"
    return value, None


def file_back_lock_errors(
    lock: dict[str, Any],
    *,
    expected_session_id: str,
    store: str,
    project: str,
    output: str,
) -> list[str]:
    errors: list[str] = []
    if lock.get("schema_version") != FILE_BACK_LOCK_SCHEMA_VERSION:
        errors.append(
            "file-back lock schema_version="
            f"{lock.get('schema_version')!r}, expected {FILE_BACK_LOCK_SCHEMA_VERSION!r}"
        )
    if lock.get("kind") != FILE_BACK_LOCK_KIND:
        errors.append(f"file-back lock kind={lock.get('kind')!r}, expected {FILE_BACK_LOCK_KIND!r}")
    expected = str(expected_session_id or "").strip()
    actual_session = str(lock.get("session_id") or "").strip()
    if not expected:
        errors.append("file-back lock check requires GRASP_SESSION_ID or --session-id")
    elif actual_session != expected:
        errors.append(f"active file-back lock session_id={actual_session!r}, expected {expected!r}")
    for key, expected_value in (("store", store), ("project", project), ("output", output)):
        actual_value = str(lock.get(key) or "")
        if actual_value != expected_value:
            errors.append(f"file-back lock {key}={actual_value!r}, expected {expected_value!r}")
    return errors


def acquire_file_back_lock(
    path: Path,
    *,
    session_id: str,
    store: str,
    project: str,
    output: str,
) -> list[str]:
    if not str(session_id or "").strip():
        return ["file-back lock acquisition requires GRASP_SESSION_ID or --session-id"]
    payload = file_back_lock_payload(session_id=session_id, store=store, project=project, output=output)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        lock, error = load_file_back_lock(path)
        if lock is None:
            return [error or f"file-back lock exists but could not be read: {path}"]
        errors = file_back_lock_errors(
            lock,
            expected_session_id=session_id,
            store=store,
            project=project,
            output=output,
        )
        if errors:
            return [
                "another file-back lock is active; finish or remove the stale lock before starting: "
                f"{path}"
            ] + errors
        return []
    except OSError as error:
        return [f"file-back lock {path} could not be acquired: {error}"]
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return []


def run_file_back_lock_check(
    path: Path,
    *,
    expected_session_id: str,
    store: str,
    project: str,
    output: str,
) -> list[str]:
    lock, error = load_file_back_lock(path)
    if lock is None:
        return [error or "file-back lock returned no JSON"]
    return file_back_lock_errors(
        lock,
        expected_session_id=expected_session_id,
        store=store,
        project=project,
        output=output,
    )


def release_file_back_lock(path: Path, *, expected_session_id: str) -> list[str]:
    lock, error = load_file_back_lock(path)
    if lock is None:
        return [error or "file-back lock returned no JSON"]
    actual_session = str(lock.get("session_id") or "").strip()
    expected = str(expected_session_id or "").strip()
    if actual_session != expected:
        return [
            f"refusing to release file-back lock {path}: "
            f"session_id={actual_session!r}, expected {expected!r}"
        ]
    try:
        path.unlink()
    except FileNotFoundError:
        return []
    except OSError as error:
        return [f"file-back lock {path} could not be released: {error}"]
    return []


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
    now: datetime | None = None,
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
    if session_events_are_only_active_claims(events, matching_events, now=now):
        return []
    first = matching_events[0]
    last = matching_events[-1]
    return [
        "session_id already exists before file-back; choose a unique GRASP_SESSION_ID: "
        f"{session_id} ({len(matching_events)} events, "
        f"first_sequence={first.get('event_sequence')}, last_sequence={last.get('event_sequence')})"
    ]


def session_events_are_only_active_claims(
    events: list[dict[str, Any]],
    matching_events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> bool:
    if not matching_events:
        return False
    if any(str(event.get("event_type") or "") != "page_claim" for event in matching_events):
        return False
    reference_time = now or datetime.now(timezone.utc)
    released_claim_ids = {
        str((event.get("payload") or {}).get("claim_event_id") or "")
        for event in events
        if str(event.get("event_type") or "") == "page_claim_release"
    }
    for event in matching_events:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id or event_id in released_claim_ids:
            return False
        expires_at = str((event.get("payload") or {}).get("expires_at") or "").strip()
        expires_timestamp = claim_expires_timestamp(expires_at)
        if expires_timestamp is None or expires_timestamp < reference_time.astimezone(timezone.utc).timestamp():
            return False
    return True


def claim_expires_timestamp(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).timestamp()


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


def latest_event_sequence(events: list[dict[str, Any]]) -> int | None:
    sequences: list[int] = []
    for event in events:
        try:
            sequences.append(int(event.get("event_sequence")))
        except (TypeError, ValueError):
            continue
    if not sequences:
        return None
    return max(sequences)


def is_missing_events_table_error(error: sqlite3.Error) -> bool:
    return isinstance(error, sqlite3.OperationalError) and "no such table: events" in str(error)


def is_missing_store_file_error(error: sqlite3.Error, store: str) -> bool:
    return (
        isinstance(error, sqlite3.OperationalError)
        and "unable to open database file" in str(error)
        and not Path(store).exists()
    )


def project_event_state(store: str, project: str) -> tuple[bool, str | None]:
    try:
        return bool(project_events(store, project)), None
    except sqlite3.Error as error:
        if is_missing_events_table_error(error) or is_missing_store_file_error(error, store):
            return False, None
        return False, f"could not inspect file-back store events: {error}"


def bootstrap_file_back_store_if_needed(
    repo: Path,
    *,
    store: str,
    project: str,
    output: str,
    require_journal: bool,
) -> list[str]:
    if require_journal:
        return []
    event_store = str(resolve_repo_path(repo, store))
    has_events, error = project_event_state(event_store, project)
    if error:
        return [error]
    if has_events:
        return []
    command = [
        sys.executable,
        "-m",
        "grasp",
        "--json",
        "--store",
        store,
        "--actor",
        DEFAULT_FILE_BACK_BOOTSTRAP_ACTOR,
        "--session-id",
        DEFAULT_FILE_BACK_BOOTSTRAP_SESSION_ID,
        "adopt-markdown",
        output,
        "--project",
        project,
        "--journal",
        DEFAULT_FILE_BACK_BOOTSTRAP_JOURNAL,
        "--replace-journal",
    ]
    completed = run_command(command, cwd=repo)
    error = require_success(completed, "grasp adopt-markdown bootstrap")
    if error:
        return [error]
    result, json_error = parse_json_output(completed.stdout, "adopt-markdown bootstrap")
    if result is None:
        return [json_error or "adopt-markdown bootstrap returned no JSON"]
    if result.get("project") != project:
        return [f"adopt-markdown bootstrap project={result.get('project')!r}, expected {project!r}"]
    return []


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
    errors.extend(file_back_store_output_pair_errors(repo, store=store, output=output))
    if errors:
        return errors

    errors.extend(
        bootstrap_file_back_store_if_needed(
            repo,
            store=store,
            project=project,
            output=output,
            require_journal=require_journal,
        )
    )
    if errors:
        return errors

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
            project_events(str(resolve_repo_path(repo, store)), project),
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
        help=(
            "Fetched git base to compare with HEAD. 'auto' prefers the current upstream branch, "
            "then origin/<current-branch>, then HEAD for no-upstream non-protected branches, "
            "then origin/main."
        ),
    )
    parser.add_argument("--skip-base-check", action="store_true", help="Skip the base divergence check.")
    parser.add_argument("--store", default=DEFAULT_FILE_BACK_STORE)
    parser.add_argument("--project", default="grasp-wiki")
    parser.add_argument("--journal", default="wiki.grasp/events.jsonl")
    parser.add_argument(
        "--session-id",
        default=os.environ.get("GRASP_SESSION_ID", ""),
        help=(
            "Session/work-unit id expected for the upcoming file-back. Defaults to $GRASP_SESSION_ID. "
            "It must be unused except for active page_claim events created by claim-page before preflight."
        ),
    )
    parser.add_argument(
        "--skip-session-uniqueness-check",
        action="store_true",
        help="Skip the unused-session-id/active-claim guard for legacy/ad hoc verification.",
    )
    parser.add_argument(
        "--preflight-stamp",
        default=DEFAULT_PREFLIGHT_STAMP,
        help="Gitignored JSON stamp written after a clean preflight and checked by postwrite.",
    )
    parser.add_argument(
        "--file-back-lock",
        default=DEFAULT_FILE_BACK_LOCK,
        help="Gitignored lock acquired after a clean preflight and released by postwrite.",
    )
    parser.add_argument(
        "--skip-preflight-stamp",
        action="store_true",
        help="Skip writing the preflight stamp for legacy/ad hoc verification.",
    )
    parser.add_argument(
        "--skip-file-back-lock",
        action="store_true",
        help="Skip the file-back lock guard for legacy/ad hoc verification.",
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
    parser.add_argument("--output", default=DEFAULT_FILE_BACK_OUTPUT)
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
        print_errors_and_recovery(errors, store=args.store, project=args.project, output=args.output)
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
        print_errors_and_recovery(errors, store=args.store, project=args.project, output=args.output)
        return 1

    lock_status = "skipped"
    if not args.skip_file_back_lock:
        lock_path = resolve_repo_path(repo, args.file_back_lock)
        errors.extend(
            acquire_file_back_lock(
                lock_path,
                session_id=args.session_id,
                store=args.store,
                project=args.project,
                output=args.output,
            )
        )
        if errors:
            print_errors_and_recovery(errors, store=args.store, project=args.project, output=args.output)
            return 1
        lock_status = str(lock_path.relative_to(repo) if lock_path.is_relative_to(repo) else lock_path)

    stamp_written = "skipped"
    if not args.skip_preflight_stamp:
        if not args.skip_base_check:
            errors.extend(check_git_base(repo, resolved_base))
        if not errors:
            sqlite_event_sequence = None
            try:
                sqlite_event_sequence = latest_event_sequence(
                    project_events(str(resolve_repo_path(repo, args.store)), args.project)
                )
            except sqlite3.Error as error:
                errors.append(f"could not inspect SQLite event sequence for preflight stamp: {error}")
        if not errors:
            payload, stamp_errors = preflight_stamp_from_repo(
                repo,
                session_id=args.session_id,
                base=None if args.skip_base_check else resolved_base,
                sqlite_event_sequence=sqlite_event_sequence,
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
            print_errors_and_recovery(errors, store=args.store, project=args.project, output=args.output)
            return 1

    print(
        "file-back preflight ok: "
        f"base={resolved_base if not args.skip_base_check else 'skipped'} "
        f"journal_mode={args.journal if require_journal else 'none'} "
        f"session={'skipped' if args.skip_session_uniqueness_check else args.session_id} "
        f"stamp={stamp_written} "
        f"lock={lock_status} "
        f"dirty_paths={','.join(paths)} "
        f"store={args.store} project={args.project} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
