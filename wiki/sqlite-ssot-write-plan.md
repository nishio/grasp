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

`1.8.22` starts the general rollback policy slice by making automatic projection-export rollback observable to agents. When a write command has already committed a SQLite event and projection export then fails, the command still records an `event_revert` rollback; with `--json`, stderr now includes `diagnostic.type=projection_export_rollback`, the target and rollback event ids, whether the compatibility journal was written, and the original export error. This works in both legacy journal and no-journal modes.

`1.8.23` adds the first explicit revert planning surface. `revert-event --dry-run` resolves the target event the same way as normal revert, runs the same current-state safety guards inside a rollback-only SQLite write transaction, and returns whether the event is currently revertible plus `reason` / `would_*` fields. It does not append `event_revert`, write a compatibility journal, export Markdown, or remove projection files. This answers the "what do we decide?" ambiguity by making dependency-aware/general revert work observable before adding any broader mutating command.

`1.8.24` adds mutating dependency-aware execution for the concrete same-page case. `revert-event --include-dependents` is SQLite-only; it collects later active same-page reversible events by `event_sequence`, reverts them in reverse order in the same SQLite transaction, then reverts the requested target. `--dry-run --include-dependents` returns the same plan without mutating store, journal, or projection.

`1.8.25` adds explicit multi-event rollback. `revert-events <event-id...>` is SQLite-only for target lookup; it validates that every requested target is an active reversible selected-project event, orders targets by reverse `event_sequence`, reverts them in one SQLite transaction, and supports `--dry-run` plan output for the same sequence.

`1.8.26` adds the first inferred work-unit planning surface. `revert-plan <event-id> --scope log-batch` is read-only and SQLite-only; it finds the `log_append` entry that closes the work unit containing the anchor event, returns active reversible events after the previous `log_append` through that closing `log_append`, checks the reverse-order plan in a rollback-only transaction, and reports the event ids to feed into `revert-events`.

`1.8.27` extends inferred planning to the concrete no-log-boundary case already covered by dependency-aware execution. `revert-plan <event-id> --scope same-page-dependents` is read-only and SQLite-only; it returns the anchor event plus later active same-page reversible events as rollback candidates, checks the reverse-order plan in a rollback-only transaction, and reports the event ids to feed into `revert-events`.

`1.8.28` adds explicit bounded sequence planning for multi-page histories without useful semantic boundaries. `revert-plan <event-id> --scope event-window --before/--after` is read-only and SQLite-only; it requires a positive window bound, keeps the anchor as an active reversible target, collects active reversible events in the requested contiguous `event_sequence` window, checks the reverse-order plan in a rollback-only transaction, and reports the event ids to feed into `revert-events`.

`1.8.29` adds explicit temporal burst planning for multi-page histories where session/actor/subject metadata is not available. `revert-plan <event-id> --scope time-burst --max-gap-seconds` is read-only and SQLite-only; it expands around the anchor through adjacent events whose `created_at` gap is within the given positive bound, stops at non-anchor `log_append` boundaries, checks the reverse-order plan in a rollback-only transaction, and reports candidate, boundary, and suggested `revert-events` data.

`1.8.30` makes the existing actor/session metadata columns usable from the CLI write path and adds the first metadata-scoped rollback plan. Global `--actor` / `--session-id` default from `GRASP_ACTOR` / `GRASP_SESSION_ID` and are stored on SQLite events written by write/revert/import-log/adopt paths. `revert-plan <event-id> --scope session` is read-only and SQLite-only; it requires a non-empty anchor `session_id`, returns selected-project events with the same session id, checks the reverse-order plan in a rollback-only transaction, and reports the event ids to feed into `revert-events`.

`1.8.31` adds the first log-content semantic rollback plan. `revert-plan <event-id> --scope subject-log` is read-only and SQLite-only; it uses the same previous/closing `log_append` boundary as log-batch, extracts subjects from the closing log summary/body via existing `[[wikilink]]` and Markdown path subject rules, keeps only matching page events plus the closing log, checks the reverse-order plan in a rollback-only transaction, and reports the event ids to feed into `revert-events`.

`1.8.32` adds a git-history-backed log page rollback plan for legacy/direct Markdown histories. `revert-plan <event-id> --scope log-page-subjects` is read-only and SQLite-only; it finds a closing `log.md` `page_update`, diffs `previous_lines` and `lines` to extract only newly added log lines, reads their `[[wikilink]]` / Markdown path subjects, keeps matching page events plus the closing log page update, checks the reverse-order plan in a rollback-only transaction, and reports the event ids to feed into `revert-events`. The regression fixture is real git history commit `3eaab75`, where `subject-log` has no closing `log_append` but the direct `log.md` update names the intended pages.

`1.8.33` adds the first page-content semantic rollback plan. `revert-plan <event-id> --scope content-subjects` is read-only and SQLite-only; it extracts `[[wikilink]]` / Markdown path subjects from the anchor event's changed lines, then keeps page events whose changed subjects or event targets overlap those anchor content subjects. It avoids initial adopt baseline events, uses the next log boundary as a scan cap when available, checks the reverse-order plan in a rollback-only transaction, and reports the event ids to feed into `revert-events`. The regression fixture is real git history commit `b644237`, where `log-page-subjects` does not select the `index.md` update but content subject overlap does.

`1.8.34` hardens the baseline side of those rollback plans. Initial adopt baseline now means leading adopt-origin `page_create` records followed by `log_entry_import` records; a later `write-page --create` page event is no longer swallowed just because it appears before the anchor. The regression keeps the `b644237` fixture but writes `sqlite-ssot-write-plan.md` before the `grasp-backlog.md` anchor, proving that `content-subjects` still includes the created page.

`1.8.35` hardens the anchor side of `content-subjects`. When an anchor event's changed lines contain no wikilink or Markdown path subjects, the planner now falls back to the anchor event target as the subject and reports `content_subject_source=anchor-target`. The regression creates a plain `Topic` page, updates another page to link `[[Topic]]`, appends a closing log mentioning `[[Topic]]`, and verifies that anchoring on the `page_create` still returns the created page, linking page update, and closing log as a read-only rollback candidate set.

`1.8.36` hardens the execution side of `content-subjects`. After semantic matching chooses page events, the planner adds any later active same-page dependents required to make those page events revertible and reports them as `dependent_event_ids`. The regression updates a page with `[[Topic]]`, then applies a later same-page cleanup line that has no subject; without the dependent closure the semantic candidate set is correct but not executable, while the new plan returns update + cleanup + closing log in reverse-safe order.

`1.8.37` applies the same dependency closure to the other inferred plans that choose page events from a broader history slice. `log-batch`, `subject-log`, `log-page-subjects`, and `content-subjects` now add required later active same-page dependents before rollback-only safety checking and report them as `dependent_event_ids`. The regression covers a closing-log-after-page-update case where a later same-page cleanup happens after the closing log; without dependency closure the semantic/log candidate set is correct but not executable.

`1.8.38` adds a purpose-specific semantic work-unit plan for version bump file-backs. `revert-plan <event-id> --scope version-bump` extracts semver tokens from the anchor event's changed lines, keeps only tokens shared by at least two events in the inferred log-bounded slice, and uses those tokens to return active reversible candidate events. This covers release/file-back histories where the intended work unit is tied by a version literal rather than wikilink subjects or Markdown paths. The regression replays git history commit `5f1b821`, where the `1.8.37` file-back changed five wiki pages and the existing subject-based scopes cannot infer the whole set.

`1.8.39` closes a dogfood gap in the explicit session boundary. The CLI already had `revert-plan --scope session`, but normal repo file-back runbooks did not require `GRASP_SESSION_ID`, so future multi-page writes could still lack the metadata needed for session-scoped recovery. `scripts/check_file_back_postwrite.py` now requires a non-empty expected session id by default and verifies that `write-status.sqlite_last_event.session_id` matches it. Runbook checker coverage makes AGENTS/CLAUDE, slash commands, the repo skill, and README document the same session marker requirement.

Dogfood in the same `1.8.39` slice used `GRASP_SESSION_ID=file-back-20260627T172244Z-session-postwrite`; postwrite passed the session guard, and `revert-plan --scope session` on the latest log page update returned the eight same-session file-back events with `revertible=true`.

`1.8.40` closes the other side of that explicit session boundary. A session marker that exists but is reused across two file-backs makes `revert-plan --scope session` over-select multiple work units. `scripts/check_file_back_preflight.py` now requires a non-empty expected session id by default and fails if selected-project SQLite events already contain that `session_id`. The normal runbook order is therefore: choose a unique `GRASP_SESSION_ID`, run preflight to prove it is unused, write with that session id, then run postwrite to prove the latest event used the same id.

Dogfood in the same `1.8.40` slice used `GRASP_SESSION_ID=file-back-20260627T174500Z-session-uniqueness`; preflight passed with the new id, and the same preflight failed as expected when rerun with the previous `file-back-20260627T172244Z-session-postwrite` id because 10 events already carried that session.

`1.8.41` closes a PR-branch continuation gap in that same preflight boundary. The previous default compared `origin/main...HEAD`, which is right for shared main but wrong when a draft PR branch already has its own pushed commits and the agent continues file-back work there. `scripts/check_file_back_preflight.py` now defaults `--base auto`: it resolves the current upstream tracking branch first and falls back to `origin/main` only when no upstream exists. Runbooks use `git fetch origin` so both main and PR branch tracking refs are fresh.

Dogfood in the same `1.8.41` slice used `GRASP_SESSION_ID=file-back-20260627T180001Z-preflight-auto-base`; on branch `codex/recovery-gap-scan`, default preflight reported `base=origin/codex/recovery-gap-scan` without requiring a manual `--base` override.

`1.8.42` adds the matching push-side ownership guard. `scripts/check_push_ownership.py` is intended to run after commit and before push. It fails on dirty worktrees, branches that are behind their upstream/remote tracking ref, and normal ship-loop pushes from protected branches (`main` / `master`). Feature branch ahead pushes and new remote branches are allowed; protected branch pushes require explicit `--allow-protected-branch` review. This closes the practical part of the parallel-agent incident where pathspec staging did not protect against pushing unrelated commits already ahead on `main`.

Dogfood in the same `1.8.42` slice confirmed the guard fails while the worktree is dirty and passes after commit on a clean feature branch based on `origin/main`.

`1.8.43` adds the write-start optimistic check between preflight and postwrite. `scripts/check_file_back_preflight.py` writes `.grasp/file-back-preflight.json` after a clean preflight with session/head/base/store/project/output. `scripts/check_file_back_postwrite.py` requires the same stamp by default and fails if the session id, pre-commit `HEAD`, base ref OID, or store/project/output no longer match. This catches a local commit or fetched base movement between preflight and file-back completion; commit-after-file-back ownership remains the job of `scripts/check_push_ownership.py`.

`1.8.44` adds the missing non-mutating write-start guard. Re-running preflight just before writing can hide a concurrent projection change because preflight imports Markdown into the store. `scripts/check_file_back_write_start.py` therefore runs after preflight and immediately before the first write command, but does not import Markdown. It checks the preflight stamp, git dirty paths, `write-status --no-journal --strict`, SQLite-authority projection, and SQLite events-derived semantic log projection. This is the repo-local response to the earlier stale-store export failure mode.

`1.8.45` adds the store/output pair guard exposed by dogfood of `1.8.44`. Using the repo file-back store `.grasp/file-back.sqlite` with a temporary output can import a temporary projection into the real store and leave temporary log events behind, making the SQLite events-derived semantic log projection stale. `scripts/check_file_back_preflight.py`, `scripts/check_file_back_write_start.py`, and `scripts/check_file_back_postwrite.py` now require either the repo default pair (`.grasp/file-back.sqlite` + `wiki`) or a temporary store paired with a temporary output.

`1.8.48` closes the fresh isolated worktree bootstrap gap in that preflight boundary. When no selected-project SQLite events exist in no-journal mode, `scripts/check_file_back_preflight.py` now runs `adopt-markdown` into the repo file-back store with a gitignored `.grasp/file-back-adopt.jsonl` audit journal before continuing to the normal import, `write-status --no-journal --strict`, and projection checks. This keeps a new `.grasp/file-back.sqlite` from failing on `semantic_log_error='event stream does not contain a page_create or page_update seed for log page'` while still avoiding tracked JSONL.

`1.8.49` narrows that bootstrap boundary after dogfood showed a fresh worktree can raise `unable to open database file` before `.grasp/` exists. The guard now resolves the store path against the repo, treats a missing store file and missing `events` table as bootstrappable empty state, and fails preflight for other SQLite errors such as locked, malformed, or unopenable existing stores instead of running adoption over an unknown database condition.

`1.8.50` adds a command-level projection clobber guard to the write commands themselves. Before `append-section`, `append-log`, `write-page`, or `rename-page` export a Git-tracked Markdown projection, they inspect dirty paths under `--output`; dirty paths outside the current target are allowed only when their file content already matches the current store projection. This stops the real dogfood failure where one unrecorded direct patch could be overwritten by a later full projection export, while still allowing multi-page file-back to proceed as `patch one page -> write-page -> patch next page`.

`1.8.51` extends the same boundary to recovery execution before mutation. `revert-event`, `revert-events`, and `revert-event --include-dependents` now compute the projection source paths for the target events before changing page state or inserting `event_revert` rows, then reject dirty Git projection paths outside that target set. This matters more than ordinary write export rollback: a late failure in recovery could otherwise leave a partially reverted store or extra `event_revert` events. Old payloads without `source_path` are resolved through the Markdown manifest by `page_id`.

`1.8.52` closes the target-side hole in that recovery guard. `1.8.51` still allowed the reverted target paths themselves to be dirty, which is correct only when the file already matches the current store projection. If a target file contains a local draft, a revert can pass the SQLite state safety check and then overwrite or remove that draft during projection export. Recovery execution now blocks dirty target paths before mutation unless their current file content exactly matches the current store projection.

`1.8.53` closes the analogous write execution target hole. `append-section`, `append-log`, `write-page`, and `rename-page` now block dirty target projection paths before mutation unless those files already match the current store projection. `write-page --from-file <target>` remains the direct patch fallback: it may intentionally use the target projection file itself as the replacement input. Dirty outside-target rollback behavior from `1.8.50` is unchanged.

`1.8.54` closes a session-marker guard gap exposed during dogfood. The repo-local postwrite guard previously checked only the latest SQLite event's `session_id`; a file-back could accidentally write an intermediate page event without `GRASP_SESSION_ID` and still pass if the final `append-log` carried the right session. Preflight stamps now record the latest SQLite `event_sequence`, and postwrite checks every event written after that baseline for the expected session id.

`1.8.55` closes the corresponding pre-write store-window gap. `scripts/check_file_back_write_start.py` now compares the preflight stamp's latest SQLite `event_sequence` with the current latest event sequence immediately before the first write command. If another writer advanced `.grasp/file-back.sqlite` after preflight, write-start fails before mutation and requires rerunning preflight instead of letting postwrite discover the mismatch after this session has already written events.

`1.8.56` adds the missing repo-local file-back lock for the multi-command window. `scripts/check_file_back_preflight.py` now acquires gitignored `.grasp/file-back.lock.json` after a clean preflight; `write-start` and `postwrite` require the same session/store/project/output lock, and postwrite releases it only after all checks pass. This does not make arbitrary direct writes impossible, but it makes normal runbook writers fail before starting when another guarded file-back is in progress.

`1.8.57` closes a source-of-truth drift found by dogfood: [[grasp-v1-implemented]] still said the current public compatibility version was `1.8.54` after package/history had moved to `1.8.56`. `tests/test_version_metadata.py` now checks the package version against [[history]] latest/current ledger lines and the implemented current-facts version, so release ledger drift fails in CI instead of being left for a later agent to notice manually.

`1.8.58` moves that guard into the normal wiki lint path. `scripts/check_wiki_version_ledger.py` checks the same package/history/current-facts consistency plus duplicate history entries and descending semver order. `scripts/lint_wiki.py` reports the version drift section and exits nonzero when the check fails, so ordinary file-back postwrite catches stale current facts without waiting for the full test suite.

`1.8.59` closes an execution gap in existing explicit rollback planning scopes. `event-window`, `time-burst`, and `session` now add required later same-page dependents before rollback-only safety checking, and report those additions as `dependent_event_ids`. The base selection remains the explicit event window, temporal burst, or session metadata set; dependency closure only makes that selected plan executable when a later same-page cleanup would otherwise block revert.

`1.8.60` closes a stale-log interpretation gap in the log query surface. `log-records` and `history` now return `result_mode: event-stream`, `current_state: false`, `current_state_hint`, and `staleness_signals[]` in JSON, and the text formatter prints the same mode/current-state header. This makes the SQLite log event surface explicit that it is historical transition data, not current page state.

`1.8.61` closes the remaining current-projection pointer gap for that surface. `history <query>` now returns `current_state_target` with handle resolution status: `resolved_unique` includes stable `read --page-id` args, `ambiguous` includes candidate page commands, `unresolved` keeps the query-level read fallback, and journal-only / unusable store contexts return `unavailable`. This keeps the event stream query useful without implying that an ambiguous historical subject maps to one current page.

`1.8.62` closes a proof gap rather than adding a new recovery surface. The real git history replay corpus now applies commit `3eaab75` as six existing-page `page_update` events, then reverts only the `grasp-backlog.md` `page_update` and verifies the mixed projection: that one page is back at the parent revision while the other five pages remain at the updated commit. Replay check and direct re-import both stay clean, so existing `page_update` revert is covered by the same real-history harness that already covered rename and page_create revert.

`1.8.63` closes a projection-side rollback gap in `rename-page`. The previous order removed the old projection file before exporting the new path, so a failed new-path export could leave SQLite rolled back but the old Markdown projection missing. Rename projection now exports the new store state first and removes the previous file only after export succeeds. A regression forces the new path to be a directory and verifies the rollback diagnostic, SQLite `event_revert`, restored current state, and preserved old projection file.

`1.8.64` closes the general partial projection write variant of the same class. `export-markdown` now reads all projection targets and preflights write target paths before writing any file. A regression uses non-git Markdown output where `A.md` would be updated before `B.md` fails as a directory, and verifies that after automatic SQLite rollback `A.md` still contains the old projection.

`1.8.65` closes the corresponding partial projection deletion gap in actual revert commands. `revert-event`, `revert-events`, and `revert-event --include-dependents` now export the reverted store state before deleting projection files made obsolete by page_create/page_rename revert. A regression forces `Old.md` to be a directory during page_rename revert export and verifies the SQLite revert lands while the pre-existing `New.md` projection is not deleted first.

`1.8.66` makes that failure state machine-readable. If actual revert commands write their revert events and then fail while exporting the reverted projection or removing obsolete projection files, `--json` now emits `diagnostic.type=revert_projection_export_failed` with the phase, target/revert event ids, pending removed files, journal status, and original error. This keeps the command from looking like an opaque crash when the store has already advanced to the reverted state.

`1.8.67` closes the legacy/ad hoc journal append variant before it can mutate authority. Write/recovery/adopt/import-log paths that still request `--journal` now preflight the append target before SQLite mutation; an unappendable path fails with `diagnostic.type=journal_append_preflight_failed` and explicitly reports that store, journal, and projection were not written. The normal repo file-back path remains `--no-journal`.

`1.8.68` hardens that preflight for permission-shaped failures: an existing regular journal file must be writable, and a missing journal path must have a writable/searchable existing parent directory before mutation starts. The regression uses a read-only JSONL file and confirms no SQLite event, projection write, or journal content is left behind.

This does **not** yet make every authority boundary final. `sync`, `acquire`, generated Markdown backup/review policy, broader native event-derived semantic page projection, and semantic multi-page work-unit inference beyond log-batch, subject-log, log-page-subjects, content-subjects, version-bump, same-page dependency, explicit event-window, time-burst, or explicit session metadata boundaries still need migration work.

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
| 5. Native review/recovery | Losing git-diffable JSONL is compensated | Rebuild `history`, `revert-event`, status, and replay/check surfaces from SQLite events/state; add a purpose-named projection diff only if needed | In progress: `write-status` shows SQLite event count / last event and strict-fails SQLite/JSONL event stream mismatch when a journal is required; `write-status --no-journal --strict` checks the SQLite-authority projection without JSONL guards and now reports SQLite events-derived semantic log projection drift; SQLite-sourced `revert-event` and projection failure rollback write state + `event_revert` atomically; projection export rollback is machine-readable via `projection_export_rollback` diagnostics; `revert-event --dry-run` reports revertibility and dependency/safety failure reasons without mutating state; `revert-event --include-dependents` reverts later active same-page reversible dependencies before the requested target; `revert-events` explicitly rolls back selected active SQLite events in reverse event sequence inside one transaction; revert execution paths now refuse dirty non-target projection paths before mutation; `revert-plan --scope log-batch` infers file-back style rollback candidates from SQLite `log_append` boundaries without mutating state; `revert-plan --scope subject-log` filters too-broad log-batches by closing log subjects without mutating state; `revert-plan --scope log-page-subjects` filters direct log page update histories by newly added log subjects without mutating state; `revert-plan --scope content-subjects` infers page-content subject overlap work units and now includes required same-page dependents without mutating state; `revert-plan --scope version-bump` infers release/file-back version update work units from shared semver tokens without mutating state; `revert-plan --scope same-page-dependents` infers the anchor plus later same-page reversible candidates when no log-batch boundary is available; `revert-plan --scope event-window` plans explicit bounded multi-page event_sequence windows without mutating state; `revert-plan --scope time-burst` plans explicit temporal multi-page bursts without mutating state; `revert-plan --scope session` plans same-session metadata work units without mutating state; preflight/postwrite now ensure new repo file-backs use a fresh session id and actually carry it, preflight resolves current upstream as the default branch base, write-start rechecks projection/stamp/store status and latest SQLite event_sequence without import before the first write, file-back lock blocks overlapping normal runbook writers, store/output pair guards stop temp dogfood from writing into the repo store, and push ownership guard stops dirty/behind/protected-branch pushes; `log-records` / `history` read SQLite log events when available, mark results as event stream rather than current state, and `history` now exposes current page resolution targets; `export-markdown --regenerate-log` uses SQLite events by default; old `write-diff` removed in `1.8.8` |
| 6. File-back cutover | Daily wiki edits use the new authority path | Update file-back skill / repo commands to call canonical SQLite write first, then export Markdown, lint, and commit projection | Done for repo-local dogfood: three consecutive file-backs used `scripts/check_file_back_preflight.py`, grasp write commands with `--no-journal --output wiki`, and `scripts/check_file_back_postwrite.py` without direct Markdown patch fallback. Preflight now includes unused session id guard, current-upstream default base resolution, a gitignored preflight stamp with latest SQLite event_sequence, a gitignored file-back lock, and a store/output pair guard; write-start checks projection/stamp/lock/store status, the same pair, and unchanged latest SQLite event_sequence without import before the first write; postwrite includes the SQLite semantic log projection guard, full session-window marker guard, preflight stamp consistency guard, lock consistency/release, and pair guard; push ownership guard runs after commit and before push, and runbook checker guards against drift |
| 7. Retire JSONL authority | Old alpha artifacts cannot mislead implementers | Mark `wiki.grasp/events.jsonl` as compatibility/audit artifact or remove it from the active path; update docs/AGENTS when the command surface changes | Done for repo-local dogfood in `1.8.18`: tracked `wiki.grasp/events.jsonl` is removed, normal runbooks use no-journal SQLite authority, and preflight guards accidental recreation |

## Immediate Next Slice

With projection policy, no-journal default preflight/write-start/postwrite checks, command-level `--no-journal`, repo runbook cutover, a 3-file-back no-journal dogfood streak, tracked JSONL retirement, SQLite-sourced `--regenerate-log`, postwrite semantic log guard, preflight/postwrite session window guards, preflight current-upstream base resolution, non-mutating write-start status and event-sequence checks, file-back lock for normal runbook writers, store/output pair guards, command-level dirty projection clobber guards for write and recovery execution including dirty write target and recovery target files, push ownership guard, native `write-status` semantic log status, machine-readable projection rollback diagnostics, rename projection failure preserving the old file, explicit event-stream/current-state markers and current page resolution targets on `history`, `revert-event --dry-run` planning, `revert-event --include-dependents` execution, `revert-events` explicit multi-event rollback, real-history page_create/page_rename/page_update revert corpus coverage, and `revert-plan` planning for dependency-complete log-batch, subject-log, log-page-subjects, content-subjects, version-bump, same-page-dependents, explicit event-window, explicit time-burst, and explicit session metadata scopes in place, the next slice is still to identify the next real recovery gap from dogfood or git history rather than add a generic inference surface. Generated Markdown backup/review policy should still be clarified only if a concrete recovery or review gap appears.

1. Identify the next real multi-page revert gap that cannot be handled by explicit event ids, active same-page dependencies, log-batch boundaries, closing log subjects, direct log page update subjects, changed content subject overlap, shared semver version-bump tokens, an explicit event-window count, an explicit time gap, or an explicit session id, preferably from dogfood or the existing git history replay corpus.
2. Add the smallest test-backed semantic surface for that concrete gap, using a purpose-specific flag or command name rather than preserving vague legacy concepts.
3. Clarify generated Markdown backup/review policy only if future dogfood exposes a concrete recovery workflow gap.

Completed in `1.7.39`: Phase 0 authority contract and Phase 1 connection/transaction helper. Completed in `1.8.0`: Phase 2 events table plus JSONL migration/query helpers. Completed in `1.8.1`: first Phase 3 command migration for `write-page` / `write-page --create`. Completed in `1.8.2`: `append-section` / `append-log` transaction migration. Completed in `1.8.3`: `rename-page` transaction migration. Completed in `1.8.4`: `write-status` SQLite event visibility. Completed in `1.8.5`: SQLite-sourced `revert-event` target lookup and state+event transaction. Completed in `1.8.6`: SQLite-sourced `log-records` / `history` for migrated `log_entry_import` rows plus `import-log-records` SQLite event insertion. Completed in `1.8.7`: `adopt-markdown` initial event insertion into SQLite events. Completed in `1.8.8`: removed unclear `write-diff` command. Completed in `1.8.9`: projection export failure rollback writes SQLite `event_revert` atomically with state revert. Completed in `1.8.10`: `write-status --strict` catches SQLite/JSONL event stream mismatch. Completed in `1.8.11`: `export-markdown` returns machine-readable `projection_policy`. Completed in `1.8.12`: write commands and `write-status` can run with `--no-journal`, leaving JSONL as optional compatibility/audit output. Completed in `1.8.13`: repo-local pre/postwrite guard scripts can also run in `--no-journal` mode. Completed in `1.8.14`: repo-local file-back runbooks default to guarded `--no-journal` path. Completed in `1.8.15`: runbook checker guards no-journal default wording in ship loops. Completed in `1.8.16`: pre/postwrite guard scripts default to no-journal and require `--with-journal` for compatibility journal audit. Completed in `1.8.17`: runbooks call guard scripts without `--no-journal`, document explicit audit, and the checker rejects stale guard spellings. Completed in 2026-06-27 dogfood: 3 consecutive repo file-backs used no-journal default pre/postwrite guards and no direct Markdown patch fallback. Completed in `1.8.18`: tracked `wiki.grasp/events.jsonl` retired and repo runbook audit path removed. Completed in `1.8.19`: `export-markdown --regenerate-log` uses SQLite events by default and keeps JSONL only as explicit legacy audit input. Completed in `1.8.20`: repo-local postwrite guard checks SQLite events-derived semantic log projection by default. Completed in `1.8.21`: `write-status` reports and strict-checks SQLite events-derived semantic log projection drift. Completed in `1.8.22`: projection export rollback diagnostics are machine-readable for journal and no-journal writes. Completed in `1.8.23`: `revert-event --dry-run` reports revertibility and `would_*` effects without mutating store/journal/projection. Completed in `1.8.24`: `revert-event --include-dependents` reverts later active same-page reversible events before the requested target and exposes the sequence in JSON/dry-run output. Completed in `1.8.25`: `revert-events` rolls back explicitly selected active SQLite events in reverse event sequence inside one transaction and exposes the sequence in dry-run output. Completed in `1.8.26`: `revert-plan --scope log-batch` infers file-back style rollback candidate sets from SQLite log_append boundaries without mutating state. Completed in `1.8.27`: `revert-plan --scope same-page-dependents` infers anchor + later same-page reversible rollback candidates without log-batch boundaries. Completed in `1.8.28`: `revert-plan --scope event-window` plans explicit bounded multi-page event_sequence windows without semantic boundary inference. Completed in `1.8.29`: `revert-plan --scope time-burst` plans explicit temporal multi-page bursts without semantic/session metadata. Completed in `1.8.30`: global actor/session metadata reaches SQLite write events and `revert-plan --scope session` plans explicit same-session work units. Completed in `1.8.31`: `revert-plan --scope subject-log` filters too-broad log-batches by closing log subjects. Completed in `1.8.32`: `revert-plan --scope log-page-subjects` filters direct log page update histories by newly added log subjects. Completed in `1.8.33`: `revert-plan --scope content-subjects` infers changed content subject overlap work units. Completed in `1.8.34`: initial adopt baseline detection no longer excludes real `write-page --create` events before the anchor. Completed in `1.8.35`: `content-subjects` falls back to the anchor target when changed lines have no subjects. Completed in `1.8.50`: write commands refuse Git dirty projection paths outside the current target unless those paths already match the current store projection. Not completed: semantic multi-page work-unit inference beyond log-batch, subject-log, log-page-subjects, content-subjects, version-bump, same-page dependency, explicit event-window, time-burst, or session boundaries, plus generated Markdown backup/review policy if a concrete gap appears.

Completed in `1.8.36`: `content-subjects` adds required same-page dependents to make semantic candidate sets executable when later cleanup edits would otherwise block revert.

Completed in `1.8.37`: `log-batch`, `subject-log`, and `log-page-subjects` now share the same required same-page dependent closure as `content-subjects`, so inferred plans that select page events are dependency-complete before safety checking.

Completed in `1.8.38`: `revert-plan --scope version-bump` now handles release/file-back version update histories where multiple page/log changes share a semver token but not useful wikilink or Markdown path subjects.

Completed in `1.8.39`: repo-local postwrite and runbook guards now require a file-back session marker, so new normal repo file-backs preserve the metadata needed by `revert-plan --scope session`. Same-slice dogfood confirmed a session-stamped file-back is session-plannable.

Completed in `1.8.40`: repo-local preflight and runbook guards now require the file-back session id to be unused before writes start, so `revert-plan --scope session` does not over-select multiple file-backs that accidentally reused the same `GRASP_SESSION_ID`.

Completed in `1.8.41`: repo-local preflight default base now resolves the current upstream tracking branch before falling back to `origin/main`, so PR-branch file-back continuation does not require a manual `--base` override.

Completed in `1.8.42`: repo-local ship loops now run `scripts/check_push_ownership.py` after commit and before push, blocking dirty worktrees, behind branches, and normal protected-branch pushes.

Completed in `1.8.55`: repo-local write-start now fails before the first write command if the current latest SQLite event_sequence differs from the preflight stamp baseline, closing the preflight-to-write-start store mutation gap.

Completed in `1.8.57`: version metadata guard now catches drift between package version, [[history]] latest/current release ledger lines, and [[grasp-v1-implemented]] current facts.

Completed in `1.8.58`: `scripts/lint_wiki.py` now runs the version ledger/current facts guard as a hard wiki lint check, backed by `scripts/check_wiki_version_ledger.py` and regression tests for current-facts drift, duplicate entries, and ordering drift.

Completed in `1.8.59`: `revert-plan --scope event-window`, `time-burst`, and `session` now add required later same-page dependents with `dependent_event_ids`, so explicit rollback plans remain executable when same-page cleanup falls outside the base window, burst, or session selection.

Completed in `1.8.60`: `log-records` / `history` now expose `result_mode: event-stream`, `current_state: false`, `current_state_hint`, and `staleness_signals[]` in JSON and text output, so historical log entry records are not silently presented as current page state.

Completed in `1.8.61`: `history <query>` now exposes `current_state_target` with `resolved_unique` / `ambiguous` / `unresolved` / `unavailable` status and stable `read --page-id` candidate commands, so an event-stream subject no longer implies a single current page when the current handle is ambiguous.

Completed in `1.8.62`: the real git history replay corpus now covers `page_update` revert inside a multi-page update sequence by applying `3eaab75`, reverting only the `grasp-backlog.md` update, and checking the mixed projection through replay and direct re-import.

Completed in `1.8.63`: `rename-page` projection export now writes the new projection before removing the previous projection file, so export failure rollback can restore SQLite state without deleting the old Markdown projection.

Completed in `1.8.64`: `export-markdown` now separates projection comparison from file writes and preflights write targets before writing, so a later projection path/read failure does not leave earlier Markdown files partially updated after SQLite rollback.

Completed in `1.8.65`: actual revert commands now export reverted store state before deleting projection files obsolete after page_create/page_rename revert, so export failure does not delete the previous visible Markdown projection first.

Completed in `1.8.66`: actual revert projection-finalization failures now return machine-readable `revert_projection_export_failed` diagnostics on `--json` stderr after revert events have been written.

Completed in `1.8.67`: legacy/ad hoc `--journal` write paths now preflight journal appendability before mutation and return `journal_append_preflight_failed` diagnostics without changing SQLite state or Markdown projection when the journal path is unappendable.

Completed in `1.8.68`: journal append preflight now rejects read-only existing journal files and unwritable existing parent directories for missing journal paths before write commands mutate SQLite state.

Completed in `1.8.56`: repo-local preflight/write-start/postwrite now use gitignored `.grasp/file-back.lock.json` to block overlapping normal runbook file-backs, and postwrite releases the lock only after all checks pass.

Completed in `1.8.43`: repo-local preflight/postwrite now use a gitignored preflight stamp to check write-start session/head/base consistency before commit.

Completed in `1.8.44`: repo-local write-start guard now checks projection/stamp/store status without importing Markdown immediately before the first write command.

Completed in `1.8.45`: repo-local preflight/write-start/postwrite now reject mixed repo-store/temp-output or temp-store/repo-output file-back contexts.

Completed in `1.8.51`: `revert-event`, `revert-events`, and `revert-event --include-dependents` now refuse dirty Git projection paths outside the recovered target set before mutating store state or inserting `event_revert` rows.

Completed in `1.8.52`: recovery execution now also refuses dirty recovered target files unless those files already match the current store projection, preventing local target drafts from being overwritten by a revert.

Completed in `1.8.53`: write execution now also refuses dirty target files before mutation unless those files already match the current store projection, while preserving `write-page --from-file <target>` as the direct patch fallback.

Completed in `1.8.54`: repo-local preflight stamps now record the latest SQLite event sequence, and postwrite validates every SQLite event written after that baseline has the expected file-back session id.

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

## Test cadence for tight rollback slices
- 2026-06-28 observation: full `python3 -m unittest discover -s tests` is about 69 seconds on this repo, and almost all of that wait is `tests/test_cli_help.py` (~35s) plus `tests/test_git_history_replay.py` (~29s). In a tight rollback-planning loop, running the full suite after every micro-slice can easily turn into tens of minutes of idle wait.
- Policy: during implementation, run the smallest targeted test that covers the touched command or fixture. Run `tests.test_git_history_replay` only when git-history replay behavior, replay fixtures, or history-backed rollback planning changed. Run `tests.test_cli_help` when CLI parser/help contracts or broad CLI JSON contracts changed.
- Ship boundary remains strict: before commit/push, run the full test suite once, plus wiki lint, runbook check, and `git diff --check`. If a commit changes file-back guards or runbooks, also run the specific guard-script tests. This keeps confidence at the boundary without paying the full-suite cost after every small edit.
