---
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git fetch:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(python3 -m unittest discover -s tests:*), Bash(python3 scripts/lint_wiki.py:*), Bash(python3 scripts/check_projection_policy.py:*), Bash(python3 scripts/check_file_back_preflight.py:*), Bash(python3 scripts/check_file_back_postwrite.py:*), Bash(python3 scripts/check_file_back_runbook.py:*), Bash(python3 scripts/check_push_ownership.py:*), Bash(python3 -m grasp:*), Bash(git diff --check:*), Bash(date:*), Bash(rg:*), Bash(sed:*), Read, Edit, MultiEdit, TodoWrite
description: File back grasp work, commit, push, and propose what to build next in Japanese
---

## Context

- Current git status: !`git status --short --branch`
- Current diff summary: !`git diff --stat`
- Current staged/unstaged diff: !`git diff HEAD`
- Recent commits: !`git log --oneline --decorate -5`

## Your task

Close the current grasp work loop: **file back, verify, commit, push, then answer "what's next?" in Japanese**

Follow these steps:

1. Inspect the diff and identify what changed. If there are no changes, do not create an empty commit; instead, report that the tree is clean and answer "what's next?" from the current wiki/backlog.
2. File back the useful facts into the development wiki before committing:
   - implemented/current behavior -> `wiki/entities/grasp-v1-implemented.md` or the relevant entity page
   - remaining work -> `wiki/grasp-backlog.md`
   - design rationale or changed decision -> `wiki/decisions/`
   - chronological record -> `wiki/log.md` using `## [YYYY-MM-DD HH:MM] <op> | <desc>`
   - keep file back factual and scoped; do not over-spec future work.
   - for grasp-write-backed file back, first set one per-file-back `GRASP_SESSION_ID`, then run `git fetch origin` and `python3 scripts/check_file_back_preflight.py` (no-journal default); preflight uses the current upstream branch as its base, falls back to `origin/main`, requires an unused session id, and writes a gitignored preflight stamp with session/head/base.
   - keep that `GRASP_SESSION_ID` for the write commands and postwrite; postwrite requires the same session id on the latest SQLite event and checks the preflight stamp session/head/base.
   - tracked `wiki.grasp/events.jsonl` was retired and removed in `1.8.18`; normal repo file-back must not recreate or commit it.
   - `--journal` / `--with-journal` remain for legacy/ad hoc CLI audits outside the normal repo runbook. Do not use repo-runbook `--with-journal`.
3. Run verification:
   - `python3 -m unittest discover -s tests`
   - `python3 scripts/lint_wiki.py`
   - `python3 scripts/check_file_back_runbook.py`
   - if file-back / projection behavior changed, `python3 scripts/check_file_back_postwrite.py` (no-journal default; includes SQLite events semantic log projection check)
   - `git diff --check`
   - If relevant, run one small dogfood command and file back any important observation.
4. Stage all intentional changes, commit once with a concise message, run `python3 scripts/check_push_ownership.py`, and push the current branch to `origin`.
5. Finish with a short Japanese summary:
   - commit hash and pushed branch
   - verification results
   - any caveat or known residual risk
   - "次にやるなら" with the top 1-3 concrete next implementation candidates from `wiki/grasp-backlog.md`, ordered by current leverage.

Constraints:

- Do not revert unrelated user changes.
- Do not commit if verification fails; report the failure and the blocking output.
- Do not push if `python3 scripts/check_push_ownership.py` fails; it blocks dirty worktrees, behind branches, and normal ship-loop pushes from protected branches such as `main`.
- Do not create a branch unless the user explicitly asked for one or the safety guard requires an isolated branch/PR.
- Use the current branch when it is not protected; normal ship-loop pushes from `main` / `master` are blocked unless an explicit ownership review chooses `--allow-protected-branch`.
