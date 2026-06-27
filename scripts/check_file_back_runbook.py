"""Check that repo file-back runbooks keep no-journal as the normal path."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunbookRule:
    path: str
    required: tuple[str, ...]
    forbidden: tuple[str, ...] = ()


DEFAULT_RULES: tuple[RunbookRule, ...] = (
    RunbookRule(
        "AGENTS.md",
        required=(
            "python3 scripts/check_file_back_preflight.py`（no-journal default）",
            "`--no-journal --output wiki`",
            "python3 scripts/check_file_back_postwrite.py`（no-journal default）",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "preflight は未使用 session id を要求",
            "postwrite は同じ session id を要求",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
            "repo runbook では `--with-journal` を使わない",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--journal wiki.grasp/events.jsonl --output wiki",
            "wiki・journal dirty",
            "repo の通常 file-back は明示 cutover",
            "transition 中の互換/audit artifact",
        ),
    ),
    RunbookRule(
        "CLAUDE.md",
        required=(
            "python3 scripts/check_file_back_preflight.py`（no-journal default）",
            "`--no-journal --output wiki`",
            "python3 scripts/check_file_back_postwrite.py`（no-journal default）",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "preflight は未使用 session id を要求",
            "postwrite は同じ session id を要求",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
            "repo runbook では `--with-journal` を使わない",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--journal wiki.grasp/events.jsonl --output wiki",
            "wiki・journal dirty",
            "repo の通常 file-back は明示 cutover",
            "transition 中の互換/audit artifact",
        ),
    ),
    RunbookRule(
        "plugins/grasp-next/commands/next.md",
        required=(
            "$PYTHON_BIN scripts/check_file_back_preflight.py",
            "この preflight は no-journal default",
            "`--output wiki --no-journal`",
            "scripts/check_file_back_postwrite.py`（no-journal default",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "未使用 session id",
            "postwrite は同じ session id を要求",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
            "repo runbook では `--with-journal` を使わない",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--journal wiki.grasp/events.jsonl --output wiki",
            "wiki/journal dirty",
            "transition 中の互換/audit artifact",
        ),
    ),
    RunbookRule(
        ".claude/commands/ship-next.md",
        required=(
            "python3 scripts/check_file_back_preflight.py` (no-journal default)",
            "python3 scripts/check_file_back_postwrite.py` (no-journal default",
            "SQLite events semantic log projection",
            "`GRASP_SESSION_ID`",
            "preflight requires an unused session id",
            "postwrite requires the same session id",
            "tracked `wiki.grasp/events.jsonl` was retired and removed in `1.8.18`",
            "Do not use repo-runbook `--with-journal`",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--journal wiki.grasp/events.jsonl --output wiki",
            "first run `git fetch origin main` and `python3 scripts/check_file_back_preflight.py`.",
        ),
    ),
    RunbookRule(
        "skills/grasp/SKILL.md",
        required=(
            "通常編集は `--no-journal` path",
            "python3 scripts/check_file_back_preflight.py`（no-journal default）",
            "python3 scripts/check_file_back_postwrite.py`（no-journal default）",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "preflight は未使用 session id",
            "postwrite は同じ session id を要求",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
        ),
        forbidden=(
            "wiki・journal dirty",
            "`--no-journal` cutover 検証時",
            "transition 中の compatibility/audit artifact",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--journal wiki.grasp/events.jsonl",
        ),
    ),
    RunbookRule(
        "README.md",
        required=(
            "repo-local file-back guard scripts は no-journal が default",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "preflight は未使用 session id を要求",
            "postwrite は同じ session id を要求",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役済み",
        ),
        forbidden=(
            "journal あり mode と `--no-journal` mode の両方を検査できる",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
        ),
    ),
)


def check_text(text: str, rule: RunbookRule) -> list[str]:
    errors: list[str] = []
    for fragment in rule.required:
        if fragment not in text:
            errors.append(f"{rule.path}: missing required fragment: {fragment}")
    for fragment in rule.forbidden:
        if fragment in text:
            errors.append(f"{rule.path}: forbidden stale fragment present: {fragment}")
    return errors


def check_runbooks(repo: Path, rules: tuple[RunbookRule, ...] = DEFAULT_RULES) -> list[str]:
    errors: list[str] = []
    for rule in rules:
        path = repo / rule.path
        if not path.exists():
            errors.append(f"{rule.path}: file does not exist")
            continue
        errors.extend(check_text(path.read_text(encoding="utf-8"), rule))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check no-journal file-back runbook defaults.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    args = parser.parse_args()

    errors = check_runbooks(Path(args.repo).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("file-back runbook ok: no-journal default, retired journal, semantic log guard, and session uniqueness marker documented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
