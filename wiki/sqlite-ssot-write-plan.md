---
type: plan
summary: 2026-06-27 現行の write authority 実装計画。旧 [[llm-wiki-infra-fast-path-plan]] の events.jsonl-first fast path を supersede し、SQLite を canonical SSoT、events を SQLite table、Markdown を export-only projection にする。目的は並行 agent write を authority 層で直列化し、file-back cutover を安全に再開できる状態を作ること。
sources:
  - [[sqlite-write-concurrency]]
  - [[native-authority-markdown-projection]]
  - [[parallel-agent-write-incident-2026-06-26]]
  - [[ai-author-feedback-2026-06-26]]
  - [[llm-wiki-infra-fast-path-plan]]
  - [[write-layer-alpha-and-replay-test]]
  - [[grasp-backlog]]
---

# SQLite SSoT write plan

## Status

This is the current implementation plan for the write authority line as of 2026-06-27.

It supersedes [[llm-wiki-infra-fast-path-plan]] as an implementation plan. The old plan remains useful as a record of `1.7.x` alpha work and as the replay-test corpus, but its authority model is obsolete: `events.jsonl` is no longer the target source of truth.

## Target Shape

- **One canonical persistent SQLite store is the source of truth** for pages, lines, handles, edges, events, and log records.
- **Events live inside SQLite**. The durable event stream is an `events` table written in the same transaction as state changes.
- **Markdown is export-only projection**. `wiki/` is still emitted for review, backup, publish, and interoperability, but normal edits do not start from Markdown patch + import.
- **Write operations are one SQLite transaction**. A write command opens the canonical store, takes the write transaction (`BEGIN IMMEDIATE` or equivalent), appends event rows, updates materialized state, and commits once.
- **Recovery is grasp-native**. `history`, `revert-event`, and export/replay checks replace the old escape hatch of manually editing `events.jsonl` / `wiki/` and using git checkout. `write-diff` was removed in `1.8.8`; if a diff/review surface becomes necessary, create a purpose-named command instead of preserving the old vague one.

## Phase 0 Authority Contract (2026-06-27)

- Canonical authoring store for a grasp-backed repository is repo-local `.grasp/authority.sqlite` by default, overridable with `$GRASP_CANONICAL_STORE`. The existing `$GRASP_STORE` / `~/.grasp/grasp.sqlite` default remains the general read/import cache path and is not automatically the wiki authoring SSoT.
- The canonical SQLite file is durable local state, but is **not git-tracked** in the current plan. It remains under `.grasp/` with other local stores. Git-tracking SQLite is deferred until there is evidence that binary review/merge cost is acceptable.
- `wiki/` remains a git-tracked Markdown projection for review, backup, publishing, and fresh-checkout recovery. It is still an output that must match the store, not the normal edit input after cutover.
- `wiki.grasp/events.jsonl` is legacy audit/migration input for the `1.7.x` fast path. New authority work must not deepen JSONL as the long-term source of truth.
- Fresh checkout recovery before Phase 2/3 is: use git-tracked `wiki/` to seed current page state, then use legacy JSONL only for audit/history where needed. After events table migration lands, recovery should import/migrate legacy JSONL into SQLite events and export Markdown from SQLite.
- Commits during the transition should include generated Markdown projection and migration/audit text artifacts, not `.grasp/authority.sqlite`.

## Phase 1 Substrate Status

`1.7.39` adds the first substrate slice: `canonical_store_path()`, write-oriented SQLite connection setup with WAL + busy timeout, and `sqlite_write_transaction()` using `BEGIN IMMEDIATE`. Tests cover WAL/busy_timeout configuration, commit/rollback, and deterministic lock contention between two writers.

`1.8.0` adds the Phase 2 events table substrate: SQLite schema v8 stores legacy journal events with monotonic sequence, event id/type/project/created_at, actor/session metadata, and canonical payload JSON. `SQLiteStore.import_journal_events()` migrates JSONL or in-memory event dicts with duplicate skip, and `SQLiteStore.events()` / `event_count()` query by project and event type.

`1.8.1` starts Phase 3 by moving `write-page` / `write-page --create` onto SQLite state+event atomic commit. The command still writes legacy `events.jsonl` and exports Markdown projection for compatibility, but the page state update and SQLite `events` insert now commit together under `BEGIN IMMEDIATE`.

`1.8.2` moves `append-section` and `append-log` onto the same SQLite state+event transaction pattern. Their legacy `events.jsonl` append and Markdown projection export continue for compatibility.

`1.8.3` moves `rename-page` / `rename` onto the same SQLite state+event transaction pattern. Their legacy `events.jsonl` append and Markdown projection export continue for compatibility.

`1.8.4` makes `write-status` show SQLite event count and last event alongside legacy JSONL journal count and last event. This was initially visibility only.

`1.8.5` moves the SQLite-sourced `revert-event` path onto SQLite events. It resolves target events from selected-project SQLite `events` first, falls back to legacy JSONL only when needed, and commits the page state revert plus SQLite `event_revert` row in the same `BEGIN IMMEDIATE` transaction. It still appends the legacy JSONL `event_revert` and exports Markdown projection for compatibility.

`1.8.6` moves the first log/history read surface onto SQLite events. `import-log-records` inserts new/updated `log_entry_import` records into SQLite `events` before appending legacy JSONL. `log-records` / `history` use SQLite `log_entry_import` rows when present and fall back to JSONL when the selected store has no migrated log record events.

`1.8.7` moves `adopt-markdown` initial event insertion into SQLite events. Initial `page_create` and `log_entry_import` records are inserted into SQLite with duplicate-skip before the compatibility JSONL append, so fresh adoption produces a SQLite event stream immediately.

`1.8.8` removes `write-diff` instead of redefining it under SQLite SSoT. The old current-filesystem-to-stored-projection diff had no clear milestone purpose once `export-markdown --check` / `write-status --strict` already covered no-op checks. A future diff/review surface should use a purpose-specific name such as `projection-diff` / `check-projection`.

`1.8.9` moves projection export failure rollback onto SQLite events. When a write event has already been committed and legacy JSONL appended but Markdown projection export fails, automatic rollback now reverts state and inserts SQLite `event_revert` in the same `BEGIN IMMEDIATE` transaction before appending the legacy JSONL `event_revert`.

`1.8.10` makes `write-status --strict` fail when selected-project SQLite events are not an ordered subsequence of the legacy JSONL journal. The comparison is by `(event_id, event_type, project)` sequence and returns `event_streams_match` / `event_stream_mismatch`. This is a transition audit guard, not a return to JSONL authority; the ordered-subsequence rule allows legacy pre-SQLite journal prefixes and compatibility-only journal records to remain as audit history.

`1.8.11` makes the export-only projection policy machine-readable. `export-markdown` now returns `projection_policy` with `authority=sqlite`, `base=stored_markdown_lines`, `output_role=git_tracked_projection`, the current check/write mode, and generated overlays such as `navigation-index` / `legacy-journal-log`. This lets ship loops and file-back cutover assert that Markdown is an output projection, not a hidden authority input.

`scripts/check_projection_policy.py` is the repo-local guard for that assertion. `/next`, `/ship-next`, AGENTS/CLAUDE, and the local file-back skill now route `export-markdown --json --check` through this checker when operating on the grasp wiki.

`scripts/check_file_back_preflight.py` wraps the guarded file-back preflight. It checks that `origin/main...HEAD` is empty after fetch, `wiki/` is clean before writes, the retired `wiki.grasp/events.jsonl` path has not been recreated or changed, `write-status --no-journal --strict` is clean, and the projection policy check passes. `--with-journal` remains an explicit legacy/ad hoc audit mode, not the repo runbook path. This moves the dogfood path from remembered command sequence to an executable gate.

`scripts/check_file_back_postwrite.py` wraps the write-after verification. It checks `write-status --no-journal --strict`, `export-markdown --json --check` projection policy, SQLite events-derived semantic log projection through `export-markdown --regenerate-log --check`, `scripts/lint_wiki.py`, and `git diff --check` after grasp writes have updated `wiki/`. With `--with-journal`, it uses the legacy JSONL guards for explicit audit work outside the repo runbook. This makes the post-write side of the dogfood loop executable too.

`1.8.14` cuts the repo-local runbooks over to `--no-journal` as the normal file-back path. AGENTS/CLAUDE, Codex `/next`, Claude `/ship-next`, and the repo `grasp` skill now call `scripts/check_file_back_preflight.py --no-journal`, write with `--no-journal --output wiki`, and verify with `scripts/check_file_back_postwrite.py --no-journal`. `wiki.grasp/events.jsonl` remains a compatibility/audit artifact for explicit audit runs, not an active dependency of normal file-back.

`1.8.15` adds `scripts/check_file_back_runbook.py` and puts it into `/next` / `/ship-next` verification. This makes the no-journal runbook default executable: if AGENTS/CLAUDE, the slash commands, the repo skill, or README drift back toward compatibility-journal default wording, the ship loop fails before commit.

`1.8.16` flips the guard scripts themselves to no-journal default. `scripts/check_file_back_preflight.py` and `scripts/check_file_back_postwrite.py` now run SQLite-authority projection checks without a flag; compatibility journal guards require explicit `--with-journal`. `--no-journal` remains accepted as an explicit compatibility flag for existing runbooks.

`1.8.17` removes the remaining stale guard-script spellings from AGENTS/CLAUDE, Codex `/next`, and Claude `/ship-next`: normal pre/postwrite guards are called without `--no-journal`, while compatibility JSONL audit requires explicit `--with-journal`. The runbook checker rejects stale `check_file_back_* --no-journal` guard instructions and requires the explicit audit path.

`1.8.18` retires the tracked repo JSONL artifact. `wiki.grasp/events.jsonl` is removed from git, normal repo file-back must not recreate it, and `scripts/check_file_back_preflight.py` treats that path as a dirty retired artifact if it appears or changes. `--journal` / `--with-journal` remain CLI legacy/ad hoc audit surfaces, but AGENTS/CLAUDE, `/next`, `/ship-next`, the repo skill, README, and the runbook checker no longer present them as repo runbook steps.

`1.8.19` moves the first semantic log projection off JSONL. `export-markdown --regenerate-log` now uses SQLite events by default and reports `sqlite-events-log`; `--journal <path>` is only the legacy/ad hoc audit source and still reports `legacy-journal-log`. Partial SQLite streams that start after `import --markdown` can seed log replay from log page `page_update` / `page_rename` / supported revert events, so the repo-local `.grasp/file-back.sqlite` passes `export-markdown --regenerate-log --check` without a journal. This is the first native events-derived semantic page projection slice after the tracked JSONL artifact was retired.

`1.8.20` promotes that semantic log projection into the repo-local default postwrite guard. `scripts/check_file_back_postwrite.py` now runs `export-markdown --regenerate-log --check` unless explicitly skipped and verifies the SQLite source/overlay contract (`log_event_source="sqlite"` and `sqlite-events-log`). The runbook checker also requires AGENTS/CLAUDE, slash commands, repo skill, and README to mention this guard.

`1.8.21` moves that signal into the native recovery/status surface. `write-status` now checks the SQLite events-derived semantic log projection whenever the Markdown project has a log page, returns `semantic_log_projection` / `semantic_log_stale` / `semantic_log_changed_files` / `semantic_log_error` / `semantic_log_policy_errors`, and fails `--strict` with `semantic_log_stale` when the generated SQLite log projection drifts. Projects without a log page skip this semantic check.

This does **not** yet make every authority boundary final. `sync`, `acquire`, generated Markdown backup/review policy, and broader native event-derived semantic page projection still need migration work.

## Why This Replaces The Fast Path

The old fast path proved that the write surface can exist: `write-page`, `rename-page`, replay, status, diff, and revert all landed. It did not prove that the authority model is safe.

The parallel agent incident showed that the previous 3-layer path has the wrong critical section:

- `events.jsonl` append is outside SQLite.
- Markdown projection export is outside SQLite.
- Store files can be stale or per-task, so SQLite locking protects only a cache layer.
- `write-page` exports the full projection, so a stale store can overwrite another agent's unjournaled Markdown patch.
- Git merge can succeed while `replay-journal --check` fails.

Therefore, adding more guards to `events.jsonl` is only a temporary mitigation. The current plan is to move the authority boundary into SQLite first, then re-enable dogfood cutover.

## Phases

| Phase | Outcome | Implementation work | Done when |
|---|---|---|---|
| 0. Authority contract | No ambiguity about what is canonical | Decide canonical store path, backup/export policy, migration story from `wiki.grasp/events.jsonl`, and whether Markdown projection remains git-tracked snapshot | A short decision/update says exactly where the SSoT lives and how another checkout recovers it |
| 1. SQLite write substrate | Concurrent writers serialize at the real authority layer | Add canonical-store open path, WAL, busy timeout, transaction helper, and a test that two writers cannot interleave state/event/projection semantics | A write transaction can update state + event rows atomically; second writer waits or fails deterministically |
| 2. Events table | JSONL is no longer the write authority | Add `events` table with monotonic sequence, event id, type, payload, actor/session metadata, created_at, and migration/import from existing JSONL where needed | Done in `1.8.0`: existing event types can be represented and queried from SQLite without reading `events.jsonl` |
| 3. Write command migration | Core write verbs update SQLite SSoT | Move `write-page`, `write-page --create`, `rename-page`, log record import, and append-style helpers to the transaction helper | Mostly complete for Markdown authoring alpha: `adopt-markdown`, `write-page` / `write-page --create`, `append-section` / `append-log`, `rename-page`, `import-log-records`, and projection export failure rollback write SQLite events |
| 4. Export-only Markdown | Projection becomes a read side effect, not authority | Make `export-markdown` read from canonical SQLite. Keep `--check`; make direct `import --markdown` an adoption/emergency path, not reconcile default | In progress: `export-markdown` returns `projection_policy` proving SQLite authority and git-tracked projection role; remaining proof is normal file-back without direct Markdown patch |
| 5. Native review/recovery | Losing git-diffable JSONL is compensated | Rebuild `history`, `revert-event`, status, and replay/check surfaces from SQLite events/state; add a purpose-named projection diff only if needed | In progress: `write-status` shows SQLite event count / last event and strict-fails SQLite/JSONL event stream mismatch when a journal is required; `write-status --no-journal --strict` checks the SQLite-authority projection without JSONL guards and now reports SQLite events-derived semantic log projection drift; SQLite-sourced `revert-event` and projection failure rollback write state + `event_revert` atomically; `log-records` / `history` read SQLite log events when available; `export-markdown --regenerate-log` uses SQLite events by default; old `write-diff` removed in `1.8.8` |
| 6. File-back cutover | Daily wiki edits use the new authority path | Update file-back skill / repo commands to call canonical SQLite write first, then export Markdown, lint, and commit projection | Done for repo-local dogfood: three consecutive file-backs used `scripts/check_file_back_preflight.py`, grasp write commands with `--no-journal --output wiki`, and `scripts/check_file_back_postwrite.py` without direct Markdown patch fallback. Postwrite now includes the SQLite semantic log projection guard, and runbook checker guards against drift |
| 7. Retire JSONL authority | Old alpha artifacts cannot mislead implementers | Mark `wiki.grasp/events.jsonl` as compatibility/audit artifact or remove it from the active path; update docs/AGENTS when the command surface changes | Done for repo-local dogfood in `1.8.18`: tracked `wiki.grasp/events.jsonl` is removed, normal runbooks use no-journal SQLite authority, and preflight guards accidental recreation |

## Immediate Next Slice

With projection policy, no-journal default preflight/postwrite checks, command-level `--no-journal`, repo runbook cutover, a 3-file-back no-journal dogfood streak, tracked JSONL retirement, SQLite-sourced `--regenerate-log`, postwrite semantic log guard, and native `write-status` semantic log status in place, the next slice is SQLite authority general revert / rollback policy. Generated Markdown backup/review policy should still be clarified only if a concrete recovery or review gap appears.

1. Define the remaining gap between current event-specific `revert-event` safety guards and a general SQLite authority revert / rollback policy.
2. Add the smallest test-backed case that exposes that gap, preferably from the existing git history replay corpus.
3. Clarify generated Markdown backup/review policy only if future dogfood exposes a concrete recovery workflow gap.

Completed in `1.7.39`: Phase 0 authority contract and Phase 1 connection/transaction helper. Completed in `1.8.0`: Phase 2 events table plus JSONL migration/query helpers. Completed in `1.8.1`: first Phase 3 command migration for `write-page` / `write-page --create`. Completed in `1.8.2`: `append-section` / `append-log` transaction migration. Completed in `1.8.3`: `rename-page` transaction migration. Completed in `1.8.4`: `write-status` SQLite event visibility. Completed in `1.8.5`: SQLite-sourced `revert-event` target lookup and state+event transaction. Completed in `1.8.6`: SQLite-sourced `log-records` / `history` for migrated `log_entry_import` rows plus `import-log-records` SQLite event insertion. Completed in `1.8.7`: `adopt-markdown` initial event insertion into SQLite events. Completed in `1.8.8`: removed unclear `write-diff` command. Completed in `1.8.9`: projection export failure rollback writes SQLite `event_revert` atomically with state revert. Completed in `1.8.10`: `write-status --strict` catches SQLite/JSONL event stream mismatch. Completed in `1.8.11`: `export-markdown` returns machine-readable `projection_policy`. Completed in `1.8.12`: write commands and `write-status` can run with `--no-journal`, leaving JSONL as optional compatibility/audit output. Completed in `1.8.13`: repo-local pre/postwrite guard scripts can also run in `--no-journal` mode. Completed in `1.8.14`: repo-local file-back runbooks default to guarded `--no-journal` path. Completed in `1.8.15`: runbook checker guards no-journal default wording in ship loops. Completed in `1.8.16`: pre/postwrite guard scripts default to no-journal and require `--with-journal` for compatibility journal audit. Completed in `1.8.17`: runbooks call guard scripts without `--no-journal`, document explicit audit, and the checker rejects stale guard spellings. Completed in 2026-06-27 dogfood: 3 consecutive repo file-backs used no-journal default pre/postwrite guards and no direct Markdown patch fallback. Completed in `1.8.18`: tracked `wiki.grasp/events.jsonl` retired and repo runbook audit path removed. Completed in `1.8.19`: `export-markdown --regenerate-log` uses SQLite events by default and keeps JSONL only as explicit legacy audit input. Completed in `1.8.20`: repo-local postwrite guard checks SQLite events-derived semantic log projection by default. Completed in `1.8.21`: `write-status` reports and strict-checks SQLite events-derived semantic log projection drift. Not completed: SQLite authority general revert / rollback policy and generated Markdown backup/review policy if a concrete gap appears.

## Carry Forward From The Old Plan

- Keep the git history replay harness. It is still the best corpus for page create/update/rename/revert behavior.
- Keep rename/identity as the highest-risk correctness target.
- Keep `write-status`, `revert-event`, and `history` as user-facing recovery concepts; rebase them onto SQLite events. Do not preserve `write-diff` without a clear workflow; create a purpose-named projection review command later if needed.
- Keep Markdown projection, but treat it as generated output and backup, not as edit input.

## Do Not Carry Forward

- Do not deepen `events.jsonl` as the long-term authority.
- Do not treat `import --markdown` as normal reconcile after cutover.
- Do not move file-back skill to unguarded shared write usage; keep `write-status --strict` and projection-policy checks in the loop until the guarded dogfood streak is clean.
- Do not rely on git staging/pathspec rules to solve authority ownership. Git ownership and grasp write ownership are separate.

## Related

- [[sqlite-write-concurrency]] — why the old 3-layer write path cannot be made safe by SQLite locks alone.
- [[native-authority-markdown-projection]] — target architecture: native authority with Markdown projection.
- [[parallel-agent-write-incident-2026-06-26]] — concrete incident that changed the concurrency requirement.
- [[ai-author-feedback-2026-06-26]] — AI authoring friction and confidence-cost evidence.
- [[grasp-backlog]] — implementation backlog that points to this plan.

## Open Questions

- Whether any future portable dump should be generated from SQLite events, and what review/recovery gap would justify it.
- What actor/session metadata is enough to attribute writes across multiple agents.
- Whether a future portable text dump/export companion is needed so `.grasp/authority.sqlite` can stay untracked without making fresh-checkout recovery depend only on generated Markdown.
