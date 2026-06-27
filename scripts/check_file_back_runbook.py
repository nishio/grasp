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
            "python3 scripts/check_file_back_preflight.py --no-journal",
            "`--no-journal --output wiki`",
            "python3 scripts/check_file_back_postwrite.py --no-journal",
            "互換/audit journal も明示的に更新する必要がある時だけ",
        ),
        forbidden=(
            "`--journal wiki.grasp/events.jsonl --output wiki`",
            "wiki・journal dirty",
            "repo の通常 file-back は明示 cutover",
        ),
    ),
    RunbookRule(
        "CLAUDE.md",
        required=(
            "python3 scripts/check_file_back_preflight.py --no-journal",
            "`--no-journal --output wiki`",
            "python3 scripts/check_file_back_postwrite.py --no-journal",
            "互換/audit journal も明示的に更新する必要がある時だけ",
        ),
        forbidden=(
            "`--journal wiki.grasp/events.jsonl --output wiki`",
            "wiki・journal dirty",
            "repo の通常 file-back は明示 cutover",
        ),
    ),
    RunbookRule(
        "plugins/grasp-next/commands/next.md",
        required=(
            "$PYTHON_BIN scripts/check_file_back_preflight.py --no-journal",
            "`--output wiki --no-journal`",
            "scripts/check_file_back_postwrite.py --no-journal",
            "互換/audit journal も明示的に更新する必要がある時だけ",
        ),
        forbidden=(
            "`--output wiki --journal wiki.grasp/events.jsonl`",
            "wiki/journal dirty",
        ),
    ),
    RunbookRule(
        ".claude/commands/ship-next.md",
        required=(
            "python3 scripts/check_file_back_preflight.py --no-journal",
            "python3 scripts/check_file_back_postwrite.py --no-journal",
        ),
        forbidden=(
            "first run `git fetch origin main` and `python3 scripts/check_file_back_preflight.py`.",
            "changed, `python3 scripts/check_file_back_postwrite.py`",
        ),
    ),
    RunbookRule(
        "skills/grasp/SKILL.md",
        required=(
            "通常編集は `--no-journal` path",
            "python3 scripts/check_file_back_preflight.py --no-journal",
            "python3 scripts/check_file_back_postwrite.py --no-journal",
        ),
        forbidden=(
            "wiki・journal dirty",
            "`--no-journal` cutover 検証時",
        ),
    ),
    RunbookRule(
        "README.md",
        required=(
            "repo-local file-back guard scripts の通常 path は `--no-journal`",
        ),
        forbidden=(
            "journal あり mode と `--no-journal` mode の両方を検査できる",
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
    print("file-back runbook ok: no-journal default documented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
