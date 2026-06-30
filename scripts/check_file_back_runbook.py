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
            "python3 scripts/check_file_back_write_start.py`（no-journal default）",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "current upstream（なければ `origin/main`）",
            "未使用 session id を要求",
            "fresh store は gitignored `.grasp/file-back-adopt.jsonl` へ bootstrap",
            "gitignored preflight stamp",
            "latest SQLite event_sequence",
            "gitignored file-back lock `.grasp/file-back.lock.json`",
            "import なしで確認",
            "file-back lock が同じ session",
            "latest SQLite event_sequence が preflight 時点から増えていない",
            "preflight stamp の session/head/base 一致",
            "file-back lock の session 一致",
            "postwrite は同じ session id を要求",
            "clean な時だけ lock を解放",
            "preflight 後に増えた全 SQLite events",
            "python3 scripts/check_push_ownership.py",
            "protected branch",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
            "repo runbook では `--with-journal` を使わない",
            "repo default store/output pair",
            "temp dogfood は temp store + temp output",
            "default store と temp output を混在させない",
            "Mode2 Markdown 直接編集は既定 reject",
            "python3 scripts/check_mode2_markdown_readonly.py",
            "`reconcile-markdown --dry-run`",
            "generic merge / queue",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "check_file_back_write_start.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--skip-file-back-lock",
            "--skip-file-back-lock-check",
            "--skip-preflight-stamp",
            "--skip-preflight-stamp-check",
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
            "python3 scripts/check_file_back_write_start.py`（no-journal default）",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "current upstream（なければ `origin/main`）",
            "未使用 session id を要求",
            "fresh store は gitignored `.grasp/file-back-adopt.jsonl` へ bootstrap",
            "gitignored preflight stamp",
            "latest SQLite event_sequence",
            "gitignored file-back lock `.grasp/file-back.lock.json`",
            "import なしで確認",
            "file-back lock が同じ session",
            "latest SQLite event_sequence が preflight 時点から増えていない",
            "preflight stamp の session/head/base 一致",
            "file-back lock の session 一致",
            "postwrite は同じ session id を要求",
            "clean な時だけ lock を解放",
            "preflight 後に増えた全 SQLite events",
            "python3 scripts/check_push_ownership.py",
            "protected branch",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
            "repo runbook では `--with-journal` を使わない",
            "repo default store/output pair",
            "temp dogfood は temp store + temp output",
            "default store と temp output を混在させない",
            "Mode2 Markdown 直接編集は既定 reject",
            "python3 scripts/check_mode2_markdown_readonly.py",
            "`reconcile-markdown --dry-run`",
            "generic merge / queue",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "check_file_back_write_start.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--skip-file-back-lock",
            "--skip-file-back-lock-check",
            "--skip-preflight-stamp",
            "--skip-preflight-stamp-check",
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
            "$PYTHON_BIN scripts/check_file_back_write_start.py",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "current upstream（なければ `origin/main`）",
            "未使用 session id",
            "fresh store は gitignored `.grasp/file-back-adopt.jsonl` へ bootstrap",
            "gitignored preflight stamp",
            "latest SQLite event_sequence",
            "gitignored file-back lock `.grasp/file-back.lock.json`",
            "import なしで確認",
            "file-back lock が同じ session",
            "latest SQLite event_sequence が preflight 時点から増えていない",
            "preflight stamp の session/head/base 一致",
            "file-back lock の session 一致",
            "postwrite は同じ session id を要求",
            "clean な時だけ lock を解放",
            "preflight 後に増えた全 SQLite events",
            "$PYTHON_BIN scripts/check_push_ownership.py",
            "protected branch",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
            "repo runbook では `--with-journal` を使わない",
            "repo default store/output pair",
            "temp dogfood は temp store + temp output",
            "default store と temp output を混在させない",
            "Mode2 Markdown 直接編集は既定 reject",
            "python3 scripts/check_mode2_markdown_readonly.py",
            "`reconcile-markdown --dry-run`",
            "generic merge / queue",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "check_file_back_write_start.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--skip-file-back-lock",
            "--skip-file-back-lock-check",
            "--skip-preflight-stamp",
            "--skip-preflight-stamp-check",
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
            "python3 scripts/check_file_back_write_start.py` (no-journal default)",
            "SQLite events semantic log projection",
            "`GRASP_SESSION_ID`",
            "preflight uses the current upstream branch as its base",
            "requires an unused session id",
            "fresh repo store bootstraps through gitignored `.grasp/file-back-adopt.jsonl`",
            "writes a gitignored preflight stamp with session/head/base",
            "latest SQLite event_sequence",
            "acquires gitignored file-back lock `.grasp/file-back.lock.json`",
            "without re-importing Markdown",
            "stamp, lock, and store status",
            "latest SQLite event_sequence has not changed since preflight",
            "checks the preflight stamp session/head/base",
            "file-back lock",
            "releases the lock only after clean postwrite",
            "postwrite requires the same session id",
            "every SQLite event written after the preflight stamp",
            "python3 scripts/check_push_ownership.py",
            "protected branches",
            "tracked `wiki.grasp/events.jsonl` was retired and removed in `1.8.18`",
            "Do not use repo-runbook `--with-journal`",
            "repo default store/output pair",
            "temporary dogfood must use a temporary store and temporary output",
            "never the repo store with a temporary output",
            "Mode2 Markdown direct edits are rejected by default",
            "python3 scripts/check_mode2_markdown_readonly.py",
            "`reconcile-markdown --dry-run`",
            "generic merge / queue",
        ),
        forbidden=(
            "check_file_back_preflight.py --no-journal",
            "check_file_back_postwrite.py --no-journal",
            "check_file_back_preflight.py --with-journal",
            "check_file_back_postwrite.py --with-journal",
            "check_file_back_write_start.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--skip-file-back-lock",
            "--skip-file-back-lock-check",
            "--skip-preflight-stamp",
            "--skip-preflight-stamp-check",
            "--journal wiki.grasp/events.jsonl --output wiki",
            "first run `git fetch origin main` and `python3 scripts/check_file_back_preflight.py`.",
        ),
    ),
    RunbookRule(
        "skills/grasp/SKILL.md",
        required=(
            "通常編集は `--no-journal` path",
            "python3 scripts/check_file_back_preflight.py`（no-journal default）",
            "python3 scripts/check_file_back_write_start.py`（no-journal default）",
            "python3 scripts/check_file_back_postwrite.py`（no-journal default）",
            "SQLite events 由来の semantic log projection",
            "`GRASP_SESSION_ID`",
            "current upstream（なければ `origin/main`）",
            "未使用 session id",
            "fresh store は gitignored `.grasp/file-back-adopt.jsonl` へ bootstrap",
            "gitignored preflight stamp",
            "latest SQLite event_sequence",
            "gitignored file-back lock `.grasp/file-back.lock.json`",
            "import なしで検査",
            "file-back lock の session 一致",
            "latest SQLite event_sequence が preflight 時点から増えていない",
            "preflight stamp の session/head/base 一致",
            "postwrite は同じ session id を要求",
            "clean な時だけ lock を解放",
            "preflight 後に増えた全 SQLite events",
            "python3 scripts/check_push_ownership.py",
            "protected branch",
            "tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済み",
            "repo default store/output pair",
            "temp dogfood は temp store + temp output",
            "default store と temp output を混在させない",
            "Mode2 Markdown 直接編集は既定 reject",
            "python3 scripts/check_mode2_markdown_readonly.py",
            "`reconcile-markdown --dry-run`",
            "generic merge / queue",
        ),
        forbidden=(
            "wiki・journal dirty",
            "`--no-journal` cutover 検証時",
            "transition 中の compatibility/audit artifact",
            "check_file_back_write_start.py --with-journal",
            "--skip-session-check",
            "--skip-session-uniqueness-check",
            "--skip-file-back-lock",
            "--skip-file-back-lock-check",
            "--skip-preflight-stamp",
            "--skip-preflight-stamp-check",
            "--journal wiki.grasp/events.jsonl",
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
    print(
        "file-back runbook ok: no-journal default, retired journal, semantic log guard, "
        "session window marker, preflight stamp, file-back lock, write-start guard, "
        "store/output pair guard, mode2 Markdown readonly guard, and push ownership guard documented"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
