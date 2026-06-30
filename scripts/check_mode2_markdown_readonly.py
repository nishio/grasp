#!/usr/bin/env python3
"""Guard that mode2 Markdown remains a read-only projection.

Mode2 means SQLite is the write authority and Markdown is a generated projection.
This script does not reconcile or merge anything. It fails loudly when Markdown
differs from the SQLite projection and points the operator at the explicit
reconcile path for intentional direct-patch or merge recovery.
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


DEFAULT_STORE = ".grasp/file-back.sqlite"
DEFAULT_PROJECT = "grasp-wiki"
DEFAULT_OUTPUT = "wiki"


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def parse_json_output(completed: subprocess.CompletedProcess[str], label: str) -> tuple[dict[str, Any] | None, str | None]:
    if not completed.stdout.strip():
        detail = (completed.stderr or "").strip()
        return None, f"{label} returned no JSON" + (f": {detail}" if detail else "")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        detail = (completed.stderr or completed.stdout).strip()
        return None, f"{label} returned invalid JSON: {error}; {detail}"
    if not isinstance(value, dict):
        return None, f"{label} returned {type(value).__name__}, expected JSON object"
    return value, None


def run_grasp_json(
    repo: Path,
    *,
    store: str,
    project: str,
    args: list[str],
) -> tuple[dict[str, Any] | None, subprocess.CompletedProcess[str], str | None]:
    command = [
        sys.executable,
        "-m",
        "grasp",
        "--json",
        "--store",
        store,
        "--project",
        project,
        *args,
    ]
    completed = run_command(command, cwd=repo)
    payload, error = parse_json_output(completed, " ".join(command))
    return payload, completed, error


def mode2_markdown_readonly_errors(
    repo: Path,
    *,
    store: str,
    project: str,
    output: str,
) -> list[str]:
    errors: list[str] = []
    projection, projection_completed, projection_error = run_grasp_json(
        repo,
        store=store,
        project=project,
        args=["export-markdown", "--output", output, "--check"],
    )
    if projection is None:
        return [projection_error or f"export-markdown failed with exit {projection_completed.returncode}"]
    errors.extend(projection_policy_errors(projection))

    status, status_completed, status_error = run_grasp_json(
        repo,
        store=store,
        project=project,
        args=["write-status", "--output", output, "--no-journal", "--strict"],
    )
    if status is None:
        errors.append(status_error or f"write-status failed with exit {status_completed.returncode}")
    elif status.get("strict_ok") is not True:
        errors.append(
            "write-status strict_ok is not true: "
            f"strict_failures={status.get('strict_failures') or []}"
        )
    return errors


def recovery_hints(*, store: str, project: str, output: str) -> list[str]:
    return [
        "mode2 Markdown policy:",
        "- reject: treat Markdown edits as invalid write input by default; write through grasp commands.",
        (
            "- adopt: if these Markdown changes are an intentional direct-patch fallback or remote merge, "
            f"inspect first with `python3 -m grasp --store {store} --project {project} "
            f"reconcile-markdown --output {output} --no-journal --dry-run`."
        ),
        (
            "- commit adoption only when the dry-run has no blockers; then run the same reconcile command "
            "without --dry-run using a fresh GRASP_SESSION_ID."
        ),
        "- merge: unsupported blockers are not auto-merged; create a purpose-named merge surface only after real dogfood needs it.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that mode2 Markdown is a read-only SQLite projection.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--store", default=DEFAULT_STORE)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    errors = mode2_markdown_readonly_errors(
        repo,
        store=args.store,
        project=args.project,
        output=args.output,
    )
    if errors:
        print("mode2 Markdown read-only guard failed", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        for hint in recovery_hints(store=args.store, project=args.project, output=args.output):
            print(hint, file=sys.stderr)
        return 1
    print(
        "mode2 Markdown read-only ok: "
        f"store={args.store} project={args.project} output={args.output} "
        "projection=clean strict=green"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
