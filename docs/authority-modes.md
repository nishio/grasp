# Authority modes: indexed evidence and SQLite-authority wikis

`grasp` supports two different authority patterns. Keeping them separate avoids
the common misunderstanding that `grasp` is only a Markdown indexer.

## Mode 1: read-only indexed evidence

Use this mode for existing corpora whose source of truth should not move yet.

Examples:

- a Markdown or Obsidian vault
- a Scrapbox / Cosense JSON export
- a generated transcript archive that is projected to Markdown
- multiple existing wikis imported through `import-forest`

The existing corpus remains the authority. `grasp` builds a local SQLite graph
beside it so an agent can run `read`, `search`, `backlinks`, `related`, and
`path` without reading the whole corpus.

```bash
python3 -m grasp --store /tmp/evidence.sqlite import --markdown ~/Notes --project notes
python3 -m grasp --store /tmp/evidence.sqlite --project notes read "Some Page"
```

This is the safest on-ramp because the original files are not rewritten.

## Mode 2: SQLite-authority wiki with Markdown projection

Use this mode when new knowledge should be authored through `grasp`.

Here the SQLite store is the authoring authority. Markdown is a projection for
review, backup, publishing, or interoperability. Writes go through commands such
as `write-page` and `append-log`, which update SQLite current state and record
SQLite events. The Markdown files are then exported from that state.

```bash
mkdir -p /tmp/triage-wiki
store=/tmp/triage.sqlite
project=security-triage

cat > /tmp/triage-wiki/Home.md <<'EOF'
# Home

- SQLite-authority security triage wiki.
EOF

python3 -m grasp --store "$store" adopt-markdown /tmp/triage-wiki --project "$project"

cat > /tmp/dispute.md <<'EOF'
---
type: security-dispute
subjects:
  - CVE-2026-0001
  - service-api
---

# CVE-2026-0001 on service-api

Question:
Is [[service-api]] exploitable through [[npm:example]] in production?

Scanner position:
- vulnerable version is present

Critique position:
- vulnerable code path is not reachable in production

Evidence needed:
- dependency path
- production route/config
- owner review
EOF

python3 -m grasp \
  --store "$store" \
  --project "$project" \
  --actor agent \
  --session-id demo-security-triage \
  write-page "CVE-2026-0001 on service-api" \
  --create \
  --path CVE-2026-0001-on-service-api.md \
  --from-file /tmp/dispute.md \
  --output /tmp/triage-wiki \
  --no-journal

python3 -m grasp --store "$store" --project "$project" write-status --output /tmp/triage-wiki --no-journal --strict
```

This mode is still an alpha authoring surface, but it is the direction used by
the repository dogfood: SQLite authority, SQLite event ledger, and Markdown
projection checks.

## Pattern: A/B evidence plus C reasoning wiki

A useful architecture is to keep old evidence corpora as read-only projects
while creating a new SQLite-authority reasoning project in the same store.

```text
Wiki A: existing design/wiki notes        -> read-only imported evidence
Wiki B: logs/transcripts/security corpus  -> read-only imported evidence
Wiki C: new triage reasoning wiki         -> SQLite-authority project
```

For a vulnerability-triage workflow, A/B might contain scanner outputs, Claude
Code transcripts, human discussion exports, and existing security notes. C can
hold derived knowledge: `security-dispute`, `security-judgment`,
`scan-observation`, `assumption`, `invalidation`, and per-file attention ledger
pages. C links back to A/B for provenance.

The agent can then ask one store for bounded graph context across all three:

```bash
python3 -m grasp --store /tmp/triage.sqlite read "CVE-2026-0001"
python3 -m grasp --store /tmp/triage.sqlite related "service-api"
```

When `--project` is omitted, retrieval commands default to whole-store scope and
label project boundaries instead of merging page identities.

## Terminology

- **SQLite-authority** means writes go through the SQLite store and Markdown is
  generated from it.
- **Markdown projection** means a readable/exportable view, not necessarily the
  source of truth.
- **Event-backed materialized store** is the current implementation model:
  `pages`, `lines`, `edges`, and `page_handles` hold current state, while
  `events` records history, sessions, reverts, and provenance. It is not a pure
  replay-only event-sourced database.
- **Soft claim** means `claim-page` / `claims` are coordination signals for
  agents, not mandatory database locks.

## When to use which mode

Use Mode 1 when you are onboarding, evaluating `grasp`, or indexing evidence
that another system still owns.

Use Mode 2 when you are creating new derived knowledge whose identity, stale
checks, rollback, and provenance should be managed by `grasp`.

For new domains, start Mode 2 with page types and frontmatter conventions. Only
promote the parts that prove useful into native commands or event types.
