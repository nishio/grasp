"""Check that the current branch is safe to push from a ship loop."""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BASE = "auto"
PROTECTED_BRANCHES = ("main", "master")


@dataclass(frozen=True)
class PushOwnershipResult:
    branch: str
    base: str | None
    head: str
    ahead_count: int
    behind_count: int
    errors: list[str]


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def require_success(completed: subprocess.CompletedProcess[str], label: str) -> str | None:
    if completed.returncode == 0:
        return None
    detail = (completed.stderr or completed.stdout).strip()
    return f"{label} failed with exit {completed.returncode}: {detail}"


def dirty_worktree_errors(status_output: str) -> list[str]:
    lines = [line for line in status_output.splitlines() if line.strip()]
    if not lines:
        return []
    return ["dirty worktree before push:\n" + "\n".join(lines)]


def protected_branch_errors(
    branch: str,
    *,
    protected_branches: tuple[str, ...],
    allow_protected_branch: bool,
) -> list[str]:
    if branch and branch in protected_branches and not allow_protected_branch:
        return [
            "refusing normal ship-loop push from protected branch "
            f"{branch}; use an isolated branch/PR or pass --allow-protected-branch "
            "after explicit ownership review"
        ]
    return []


def split_left_right(log_output: str) -> tuple[list[str], list[str], list[str]]:
    left: list[str] = []
    right: list[str] = []
    other: list[str] = []
    for line in log_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("< "):
            left.append(stripped)
        elif stripped.startswith("> "):
            right.append(stripped)
        else:
            other.append(stripped)
    return left, right, other


def push_divergence_errors(log_output: str, base: str) -> list[str]:
    left, _right, other = split_left_right(log_output)
    errors: list[str] = []
    if left:
        errors.append(f"branch is behind {base}; rebase/merge before push:\n" + "\n".join(left))
    if other:
        errors.append(f"unexpected git log --left-right output for {base}...HEAD:\n" + "\n".join(other))
    return errors


def current_branch(repo: Path) -> tuple[str | None, str | None]:
    branch = run_command(["git", "branch", "--show-current"], cwd=repo)
    error = require_success(branch, "git branch --show-current")
    if error:
        return None, error
    branch_name = branch.stdout.strip()
    if not branch_name:
        return None, "detached HEAD cannot be pushed by the normal ship loop"
    return branch_name, None


def current_head(repo: Path) -> tuple[str | None, str | None]:
    head = run_command(["git", "rev-parse", "HEAD"], cwd=repo)
    error = require_success(head, "git rev-parse HEAD")
    if error:
        return None, error
    return head.stdout.strip(), None


def verify_ref(repo: Path, ref: str) -> bool:
    verified = run_command(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo)
    return verified.returncode == 0


def resolve_push_base(repo: Path, branch: str, requested_base: str) -> str | None:
    if requested_base == "none":
        return None
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
    origin_branch = f"origin/{branch}"
    if verify_ref(repo, origin_branch):
        return origin_branch
    return None


def check_push_base(repo: Path, base: str) -> tuple[list[str], int, int]:
    verify = run_command(["git", "rev-parse", "--verify", "--quiet", base], cwd=repo)
    error = require_success(verify, f"git rev-parse {base}")
    if error:
        return [error], 0, 0
    divergence = run_command(
        ["git", "log", "--left-right", "--cherry-pick", "--oneline", f"{base}...HEAD"],
        cwd=repo,
    )
    error = require_success(divergence, f"git log {base}...HEAD")
    if error:
        return [error], 0, 0
    left, right, _other = split_left_right(divergence.stdout)
    return push_divergence_errors(divergence.stdout, base), len(right), len(left)


def run_push_ownership_check(
    repo: Path,
    *,
    requested_base: str = DEFAULT_BASE,
    protected_branches: tuple[str, ...] = PROTECTED_BRANCHES,
    allow_protected_branch: bool = False,
) -> PushOwnershipResult:
    errors: list[str] = []
    branch, error = current_branch(repo)
    if error:
        errors.append(error)
        branch = ""
    head, error = current_head(repo)
    if error:
        errors.append(error)
        head = ""
    if branch:
        errors.extend(
            protected_branch_errors(
                branch,
                protected_branches=protected_branches,
                allow_protected_branch=allow_protected_branch,
            )
        )

    status = run_command(["git", "status", "--porcelain=v1"], cwd=repo)
    error = require_success(status, "git status")
    if error:
        errors.append(error)
    else:
        errors.extend(dirty_worktree_errors(status.stdout))

    base = resolve_push_base(repo, branch, requested_base) if branch else None
    ahead_count = 0
    behind_count = 0
    if base:
        base_errors, ahead_count, behind_count = check_push_base(repo, base)
        errors.extend(base_errors)

    return PushOwnershipResult(
        branch=branch,
        base=base,
        head=head,
        ahead_count=ahead_count,
        behind_count=behind_count,
        errors=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check guarded current-branch push ownership conditions.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help="Fetched git base to compare with HEAD. 'auto' prefers the current upstream branch, then origin/<branch>; use 'none' for a new remote branch.",
    )
    parser.add_argument(
        "--allow-protected-branch",
        action="store_true",
        help="Allow pushing from main/master after an explicit ownership review.",
    )
    parser.add_argument(
        "--protected-branch",
        action="append",
        dest="protected_branches",
        help="Branch name to block by default. Defaults to main and master.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    protected = tuple(args.protected_branches) if args.protected_branches else PROTECTED_BRANCHES
    result = run_push_ownership_check(
        repo,
        requested_base=args.base,
        protected_branches=protected,
        allow_protected_branch=args.allow_protected_branch,
    )
    if result.errors:
        for error in result.errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "push ownership ok: "
        f"branch={result.branch} "
        f"base={result.base or 'none'} "
        f"ahead={result.ahead_count} "
        f"behind={result.behind_count} "
        f"head={result.head}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
