# grasp

[Japanese README](README.ja.md)

**A local graph reader for AI agents.**

`grasp` treats a collection of wikis as one local graph forest. Each wiki may
be a Markdown folder, an Obsidian vault, or a Scrapbox / Cosense export.
`grasp` normalizes them into project-scoped graph nodes and edges, so an AI
agent can read across the forest from the command line without caring which
source format each wiki came from.

You can start without moving your source of truth: keep a Markdown folder, an
Obsidian vault, or a Scrapbox / Cosense project as the authoring home, and use
`grasp` as the read layer beside it. If you later want `grasp` to become the
authoring store, that migration can be gradual.

There are two authority modes:

- **Read-only indexed evidence**: keep existing Markdown, Obsidian, or
  Scrapbox / Cosense data as the source of truth and let `grasp` build a
  disposable graph index beside it.
- **SQLite-authority wiki**: create new knowledge through `grasp` writes, store
  the current state and event ledger in SQLite, and export Markdown as a
  projection for review or interoperability.

See [docs/authority-modes.md](docs/authority-modes.md) for the A/B evidence +
C reasoning-wiki pattern.

It is built for questions like:

> What have I written about this idea? Also show the lines that link to it and
> nearby pages that may matter.

## The Basic Idea

Scrapbox / Cosense are wiki-style note systems where pages are connected by
inline links, backlinks, and related pages. You do not need to know those tools
to use `grasp`. The useful idea is simple: notes are more than separate files.
Their links form a graph.

Plain file search can find matching text, but an agent still has to rebuild the
surrounding context by opening files, following links, and searching again.
`grasp` stores the links as graph edges first, so one command can return a
bounded bundle of context:

- the page body
- line-level backlinks
- related pages found through nearby links
- linked concepts that do not have their own page yet

That makes `grasp` less like a note editor and more like a local retrieval
surface for agents.

## Install

Python 3.10 or newer is required. Runtime dependencies are stdlib-only.

```bash
git clone https://github.com/nishio/grasp.git
cd grasp
pip install -e .
```

If you do not want to install it yet, run commands from the repository with
`python3 -m grasp ...`.

## Try It

This repository contains its own Markdown wiki, so you can try `grasp` without
preparing data.

```bash
grasp --store /tmp/grasp-demo.sqlite import --markdown wiki --project grasp-wiki
grasp --store /tmp/grasp-demo.sqlite --project grasp-wiki read grasp-v1-implemented --line-limit 20
```

The second command prints the page plus backlinks, related pages, and unresolved
targets when they exist.

For a smaller external-facing Markdown demo, use the bundled dense vault:

```bash
python3 -m grasp --store /tmp/persona2a.sqlite import --markdown examples/persona2a-vault --project persona2a
python3 -m grasp --store /tmp/persona2a.sqlite --project persona2a read "Ingestion Pipeline"
```

The full walkthrough is in [docs/persona2a-demo.md](docs/persona2a-demo.md).

## Use a Wiki Forest

The target is not a file format. The target is the wiki forest: many wiki trees
that can be read as one graph while keeping their project identities.

```text
Markdown wiki     Obsidian vault     Cosense export
      \                |                  /
       \               |                 /
             grasp graph store
        project-scoped nodes and edges
        backlinks / related / path / unresolved
                    |
               AI agent reads
```

For a Markdown / Obsidian registry, import the forest with:

```bash
grasp import-forest /path/to/wikis.yaml --markdown-exclude-dir raw
grasp search "some phrase"
grasp backlinks "Some Concept"
```

Scrapbox / Cosense exports can be imported into the same SQLite store with their
own `--project` names. Retrieval commands default to the whole store when
`--project` is omitted, and results keep project labels instead of merging page
identities.

## Use Your Notes

For Markdown or Obsidian-style notes:

```bash
grasp import --markdown ~/Notes --project notes
grasp --project notes read "Some Page"
grasp --project notes search "some phrase" --context 2
```

For a Scrapbox / Cosense JSON export:

```bash
grasp import --cosense your-project.json --project my-wiki
grasp --project my-wiki read "Some Page"
grasp --project my-wiki backlinks "Some Concept"
```

The default store is `~/.grasp/grasp.sqlite`. A single store can hold multiple
project namespaces; choose one with `--project`.

## Use It Through an Agent

Humans can run the CLI directly, but the intended use is to give the CLI to an
AI agent. The agent can search, read, follow backlinks, and gather a bounded
neighborhood before answering.

For Claude Code, you can symlink the bundled skill:

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/grasp" ~/.claude/skills/grasp
```

Then ask in natural language, for example:

> In my notes, what did I write about graph retrieval? Follow related pages too.

Exact command arguments and JSON shapes are documented by the CLI itself:

```bash
grasp <command> --help
grasp read --help
```

## Current Scope

Stable:

- read-only Markdown folder import
- Markdown / Obsidian forest import from a `wikis.yaml` registry
- Scrapbox / Cosense JSON export import
- local SQLite store with multiple projects
- `read`, `search`, `backlinks`, `related`, `path`, `suggest`, and `unresolved`
  with whole-store defaults when `--project` is omitted
- cross-project links and inferred normalized-title matches as labeled graph
  edges (`project`, `target_project`, `link_kind`, `connection_strength`)
- missing linked concepts as graph nodes with backlink context

Not the goal:

- Web UI
- hosted note editing
- realtime multi-user collaboration
- forcing an up-front migration of your existing note source of truth

Markdown-backed write commands exist, but they are alpha surfaces for repository
dogfooding. Treat `grasp` as a read and retrieval layer unless you are working
on the project itself or intentionally prototyping a SQLite-authority wiki.

More detailed Japanese walkthroughs are in [docs/markdown.md](docs/markdown.md)
and [docs/cosense.md](docs/cosense.md). The authority-mode guide is in
[docs/authority-modes.md](docs/authority-modes.md).

## License

MIT
