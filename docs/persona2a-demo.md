# Persona2a demo: a dense Markdown vault for agents

This demo is for persona2a: someone with a dense Markdown or Obsidian-like
vault who wants an AI agent to read project memory without first migrating the
vault into a new app.

The goal is not to show faster grep. The goal is to show that one graph read can
return the page, line-level backlinks, related pages, unresolved targets, and
write-loop guardrails that an agent needs before answering or editing.

## Run the demo

Copy the bundled vault to a temp directory so the write loop does not modify the
repository example.

```bash
tmp="$(mktemp -d)"
cp -R examples/persona2a-vault "$tmp/vault"
store="$tmp/persona2a.sqlite"
project="persona2a"
```

Import the copied Markdown vault as a read-only mirror.

```bash
python3 -m grasp --store "$store" import --markdown "$tmp/vault" --project "$project"
```

Ask the concrete agent question: what should be read before changing the
ingestion pipeline?

```bash
python3 -m grasp --store "$store" --project "$project" search "ingestion pipeline" --context 1 --limit 5
python3 -m grasp --store "$store" --project "$project" read "Ingestion Pipeline" --line-limit 20 --backlinks-limit 5 --related-limit 5 --unresolved-limit 5
python3 -m grasp --store "$store" --project "$project" backlinks "Context Budget" --limit 10
python3 -m grasp --store "$store" --project "$project" related "Ingestion Pipeline" --limit 10
python3 -m grasp --store "$store" --project "$project" gather "Context Budget" --budget 1200
```

For comparison, run plain grep:

```bash
rg -n "ingestion pipeline|Context Budget|stale write" "$tmp/vault"
```

The grep output finds lines. The `grasp read` output should also show the pages
that point at the target, nearby graph context, and unresolved concepts such as
`Frontmatter Normalizer`.

## Show the write guard

The write path is alpha, so this demo writes only to the temp copy. It appends a
session-close log entry and then verifies that the SQLite-authority projection is
clean.

```bash
python3 -m grasp \
  --store "$store" \
  --project "$project" \
  --actor demo \
  --session-id persona2a-demo \
  append-log \
  --op demo \
  --summary "capture retrieval answer" \
  --line "- Answer cites [[Ingestion Pipeline]], [[Context Budget]], and [[Stale Write Guard]]." \
  --output "$tmp/vault" \
  --no-journal

python3 -m grasp --store "$store" --project "$project" write-status --output "$tmp/vault" --no-journal --strict
```

The expected status is clean. This is the external-facing story: existing
Markdown remains the on-ramp, `grasp` supplies bounded graph context for the
agent, and the write loop has an explicit guard instead of trusting chat memory.
