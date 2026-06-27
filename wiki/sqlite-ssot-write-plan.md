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
- **Recovery is grasp-native**. `history`, `write-diff`, `revert-event`, and export/replay checks replace the old escape hatch of manually editing `events.jsonl` / `wiki/` and using git checkout.

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

This does **not** yet make every write command atomic at the new authority boundary. `rename-page`, `append-*`, `sync`, and `acquire` can open write-configured connections, but their state change + event insert + projection export migration is still Phase 3 work.

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
| 3. Write command migration | Core write verbs update SQLite SSoT | Move `write-page`, `write-page --create`, `rename-page`, log record import, and append-style helpers to the transaction helper | In progress: `write-page` / `write-page --create` commit state + SQLite event atomically; remaining write verbs still need migration |
| 4. Export-only Markdown | Projection becomes a read side effect, not authority | Make `export-markdown` read from canonical SQLite. Keep `--check`; make direct `import --markdown` an adoption/emergency path, not reconcile default | Fresh export is stable, no-op diff is clean, and normal file-back never needs Markdown direct patch |
| 5. Native review/recovery | Losing git-diffable JSONL is compensated | Rebuild `history`, `write-diff`, `revert-event`, status, and replay/check surfaces from SQLite events/state | A bad write can be diagnosed and reverted without hand-editing JSONL or Markdown |
| 6. File-back cutover | Daily wiki edits use the new authority path | Update file-back skill / repo commands to call canonical SQLite write first, then export Markdown, lint, and commit projection | Three consecutive file-backs land through SQLite SSoT without direct Markdown patch fallback |
| 7. Retire JSONL authority | Old alpha artifacts cannot mislead implementers | Mark `wiki.grasp/events.jsonl` as legacy import/audit artifact or remove it from the active path; update docs/AGENTS when the command surface changes | No current instruction tells Codex to treat JSONL as the write authority |

## Immediate Next Slice

Do not start with file-back integration. Continue from the authority substrate into events.

1. Port `append-section` / `append-log` to the same state + SQLite event transaction helper.
2. Port `rename-page`, including projection file rename and rollback semantics.
3. Rebase `revert-event`, `write-status`, `write-diff`, and `history` onto SQLite events rather than JSONL-only reads.
4. Only then move file-back workflow.

Completed in `1.7.39`: Phase 0 authority contract and Phase 1 connection/transaction helper. Completed in `1.8.0`: Phase 2 events table plus JSONL migration/query helpers. Completed in `1.8.1`: first Phase 3 command migration for `write-page` / `write-page --create`. Not completed: remaining command migration, SQLite-native recovery surfaces, file-back cutover.

## Carry Forward From The Old Plan

- Keep the git history replay harness. It is still the best corpus for page create/update/rename/revert behavior.
- Keep rename/identity as the highest-risk correctness target.
- Keep `write-status`, `write-diff`, `revert-event`, and `history` as user-facing recovery concepts; rebase them onto SQLite events.
- Keep Markdown projection, but treat it as generated output and backup, not as edit input.

## Do Not Carry Forward

- Do not deepen `events.jsonl` as the long-term authority.
- Do not treat `import --markdown` as normal reconcile after cutover.
- Do not move file-back skill to shared write usage until SQLite SSoT phases 1-5 are in place.
- Do not rely on git staging/pathspec rules to solve authority ownership. Git ownership and grasp write ownership are separate.

## Related

- [[sqlite-write-concurrency]] — why the old 3-layer write path cannot be made safe by SQLite locks alone.
- [[native-authority-markdown-projection]] — target architecture: native authority with Markdown projection.
- [[parallel-agent-write-incident-2026-06-26]] — concrete incident that changed the concurrency requirement.
- [[ai-author-feedback-2026-06-26]] — AI authoring friction and confidence-cost evidence.
- [[grasp-backlog]] — implementation backlog that points to this plan.

## Open Questions

- Exact migration policy for existing `wiki.grasp/events.jsonl`: one-time import, legacy audit read path, or discard after projection verification.
- What actor/session metadata is enough to attribute writes across multiple agents.
- Whether a future portable text dump/export companion is needed so `.grasp/authority.sqlite` can stay untracked without making fresh-checkout recovery depend only on generated Markdown.
