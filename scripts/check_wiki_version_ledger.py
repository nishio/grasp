"""Check package, release ledger, and current-facts version consistency."""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


def required_match(pattern: str, text: str, label: str) -> tuple[str | None, str | None]:
    match = re.search(pattern, text)
    if match is None:
        return None, f"{label} is missing"
    return match.group(1), None


def semver_key(version: str) -> tuple[int, int, int] | None:
    parts = version.split(".")
    if len(parts) != 3:
        return None
    try:
        return tuple(int(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def wiki_version_ledger_errors(
    *,
    pyproject_text: str,
    init_text: str,
    history_text: str,
    implemented_text: str,
) -> list[str]:
    errors: list[str] = []
    pyproject_version, error = required_match(
        r'(?m)^version = "([^"]+)"$',
        pyproject_text,
        "pyproject.toml [project] version",
    )
    if error:
        errors.append(error)
    init_version, error = required_match(
        r'(?m)^__version__ = "([^"]+)"$',
        init_text,
        "grasp.__version__",
    )
    if error:
        errors.append(error)

    history_versions = re.findall(r"(?m)^- `([^`]+)`（更新:", history_text)
    if not history_versions:
        errors.append("history latest version entry is missing")
    duplicate_versions = sorted(version for version, count in Counter(history_versions).items() if count > 1)
    if duplicate_versions:
        errors.append("history contains duplicate version entries: " + ", ".join(duplicate_versions))
    sortable_versions = [(version, semver_key(version)) for version in history_versions]
    invalid_versions = [version for version, key in sortable_versions if key is None]
    if invalid_versions:
        errors.append("history contains invalid semver entries: " + ", ".join(invalid_versions))
    if history_versions and not invalid_versions:
        highest_version = max(history_versions, key=lambda version: semver_key(version) or (0, 0, 0))
        latest_version = history_versions[0]
        if latest_version != highest_version:
            errors.append(f"history latest entry={latest_version!r}, expected highest version {highest_version!r}")
        expected_order = sorted(history_versions, key=lambda version: semver_key(version) or (0, 0, 0), reverse=True)
        if history_versions != expected_order:
            errors.append("history version entries are not in descending semver order")

    history_current, error = required_match(
        r"(?m)^- Current public compatibility version: `([^`]+)`$",
        history_text,
        "history current public compatibility version",
    )
    if error:
        errors.append(error)
    history_package, error = required_match(
        r"(?m)^- Current package metadata should match `([^`]+)`;",
        history_text,
        "history package metadata version",
    )
    if error:
        errors.append(error)
    implemented_current, error = required_match(
        r"(?m)^- current public compatibility version は `([^`]+)`。",
        implemented_text,
        "grasp-v1-implemented current public compatibility version",
    )
    if error:
        errors.append(error)

    expected = pyproject_version
    if expected:
        comparisons = (
            ("grasp.__version__", init_version),
            ("history latest entry", history_versions[0] if history_versions else None),
            ("history current public compatibility version", history_current),
            ("history package metadata version", history_package),
            ("grasp-v1-implemented current public compatibility version", implemented_current),
        )
        for label, actual in comparisons:
            if actual is not None and actual != expected:
                errors.append(f"{label}={actual!r}, expected package version {expected!r}")
    return errors


def version_ledger_errors(repo: Path) -> list[str]:
    return wiki_version_ledger_errors(
        pyproject_text=(repo / "pyproject.toml").read_text(encoding="utf-8"),
        init_text=(repo / "grasp" / "__init__.py").read_text(encoding="utf-8"),
        history_text=(repo / "wiki" / "history.md").read_text(encoding="utf-8"),
        implemented_text=(repo / "wiki" / "entities" / "grasp-v1-implemented.md").read_text(encoding="utf-8"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check wiki release ledger and current facts version consistency.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    errors = version_ledger_errors(repo)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    pyproject_version = required_match(
        r'(?m)^version = "([^"]+)"$',
        (repo / "pyproject.toml").read_text(encoding="utf-8"),
        "pyproject.toml [project] version",
    )[0]
    print(f"wiki version ledger ok: version={pyproject_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
