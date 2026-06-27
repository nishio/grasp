"""Validate export-markdown JSON as a SQLite-authority projection check.

Usage:
  python3 -m grasp --json --project grasp-wiki export-markdown --output wiki --check \
    | python3 scripts/check_projection_policy.py
"""
import argparse
import json
import sys
from typing import Any


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def load_stdin_json() -> dict[str, Any] | None:
    try:
        value = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        fail(f"invalid JSON on stdin: {error}")
        return None
    if not isinstance(value, dict):
        fail("expected JSON object on stdin")
        return None
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that export-markdown reported a clean SQLite-authority projection."
    )
    parser.add_argument("--authority", default="sqlite")
    parser.add_argument("--base", default="stored_markdown_lines")
    parser.add_argument("--output-role", default="git_tracked_projection")
    parser.add_argument("--write-mode", default="check", help="Expected write_mode, or 'any'.")
    args = parser.parse_args()

    result = load_stdin_json()
    if result is None:
        return 1
    if result.get("ok") is not True:
        return fail(
            "projection is not clean: "
            f"changed={result.get('changed_files') or []} "
            f"missing={result.get('missing_files') or []} "
            f"extra={result.get('extra_files') or []}"
        )
    policy = result.get("projection_policy")
    if not isinstance(policy, dict):
        return fail("missing projection_policy object")

    expected = {
        "authority": args.authority,
        "base": args.base,
        "output_role": args.output_role,
    }
    for key, expected_value in expected.items():
        if policy.get(key) != expected_value:
            return fail(f"projection_policy.{key}={policy.get(key)!r}, expected {expected_value!r}")
    if args.write_mode != "any" and policy.get("write_mode") != args.write_mode:
        return fail(f"projection_policy.write_mode={policy.get('write_mode')!r}, expected {args.write_mode!r}")

    overlays = policy.get("generated_overlays")
    if not isinstance(overlays, list):
        return fail("projection_policy.generated_overlays must be a list")
    print(
        "projection_policy ok: "
        f"authority={policy['authority']} "
        f"base={policy['base']} "
        f"output_role={policy['output_role']} "
        f"write_mode={policy.get('write_mode')} "
        f"generated_overlays={','.join(str(item) for item in overlays) or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
