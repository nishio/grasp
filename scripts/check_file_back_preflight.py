"""Check that grasp write-first file-back can start safely.

The check is intentionally repo-facing: run it after fetching the upstream base
and before any grasp write command touches wiki/. The default mode is
no-journal; compatibility journal checks are explicit opt-in.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_projection_policy import projection_policy_errors


DEFAULT_DIRTY_PATHS = ("wiki", "wiki.grasp/events.jsonl")
DEFAULT_NO_JOURNAL_DIRTY_PATHS = ("wiki",)


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
    return ["dirty wiki/journal paths before file-back:\n" + "\n".join(lines)]


def base_divergence_errors(log_output: str, base: str) -> list[str]:
    lines = [line for line in log_output.splitlines() if line.strip()]
    if not lines:
        return []
    return [f"branch differs from {base}; reconcile before file-back:\n" + "\n".join(lines)]


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
    if require_journal:
        if result.get("journal_exists") is not True:
            errors.append("write-status journal_exists is not true")
        if result.get("event_streams_match") is not True:
            errors.append("write-status event_streams_match is not true")
        if result.get("journal_log_stale") is True:
            errors.append("write-status journal_log_stale is true")
    return errors


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
    parser.add_argument("--base", default="origin/main", help="Fetched git base to compare with HEAD.")
    parser.add_argument("--skip-base-check", action="store_true", help="Skip the base divergence check.")
    parser.add_argument("--store", default=".grasp/file-back.sqlite")
    parser.add_argument("--project", default="grasp-wiki")
    parser.add_argument("--journal", default="wiki.grasp/events.jsonl")
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
        help="Path that must be clean before file-back. Defaults to wiki and wiki.grasp/events.jsonl; with --no-journal, defaults to wiki only.",
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
    if not args.skip_base_check:
        errors.extend(check_git_base(repo, args.base))
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
        )
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "file-back preflight ok: "
        f"base={args.base if not args.skip_base_check else 'skipped'} "
        f"journal_mode={args.journal if require_journal else 'none'} "
        f"dirty_paths={','.join(paths)} "
        f"store={args.store} project={args.project} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
