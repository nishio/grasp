---
type: entity
summary: Page cards, project-qualified connections and provenance-preserving VT analysis snapshots over grasp's existing notes and media sidecar.
sources:
  - grasp/cards.py
  - grasp/gyazo.py
  - grasp/cli.py
  - tests/test_cards.py
---
# page-cards-and-image-analysis

## Contract

`cards --query TEXT --saved-only --limit 40 --offset 0` returns one card per page, with stable `(project,id)`, title, leading text, and a cached-image preview. `--project` restricts the namespace; omitted means the whole store. Query is a literal substring of title, body or imported analysis record. Pagination uses a deterministic updated/project/id ordering and provides total/next_offset. Default limit 40, max 100. `--saved-only` uses cache metadata; missing files become non-displayable images instead of remote loads.

`--project PROJECT cards --page-id ID` returns explicit strong outgoing/incoming graph edges, shared-image references, same-title matches in other projects, and analyses joined by Gyazo ID. Categories are separate: same title is not proof of a relation; a shared image is not a semantic identity claim. Each category is limited to 100 with a truncated flag. Page IDs must always be accompanied by a project. Source reads are attached with `mode=ro`; note schema, content and events are unchanged.

Media references come from [[gyazo-local-media]]. Run `images scan` without a project first to include Wiki forest and Cosense in the same store. Cards do not implicitly import/hydrate missing notes or read unrelated stores. Thumbnails use original saved cache files; generated reduced-resolution derivatives are not yet provided.

## VT snapshot adapter

`images import-vt --vt-dir /path/to/vt-data` reads the existing named `catalog-image-map-2026-08-03.json` and `structure-descriptions-2026-08-03.json` files, joining numeric catalog ID to `vt-NNN` description ID. An optional `historical-ai-search-index-2026-08-13.json` contributes hash-keyed descriptions and review records. These are existing format adapters, not a general arbitrary-JSON importer.

The grasp media sidecar owns the derived `image_analyses` table. Each source analysis record has its own identity, preserving multiple interpretations of a single image. Description provenance is AI; human review provenance/decision is retained separately, and canonical catalog inclusion does not fabricate an acceptance record. Source filenames, SHA256 and supplied image provenance are retained. No review is performed or verdict changed. No network requests or source-file writes occur. All sources are validated before atomic snapshot replacement. A new import replaces this one connected VT dataset; live watching and multiple independent VT datasets are not implemented.

## Validation and scope

Fixture tests cover pagination, escaped literal search, duplicate page IDs in different projects, explicit links vs same-title suggestions, shared images, structural-analysis search, source-note byte immutability, source-analysis file immutability and all-or-nothing import failure. [[grasp-v1-implemented]] records the current version; [[grasp-backlog]] holds unfinished acquisition and rendering work.

## Open Questions

Separate-store federation, live Wiki forest refresh, per-page full materialization, semantic similarity of diagrams, original-source editing, and thumbnail generation are future work. Source coverage is the current imported snapshot. UI consumers must preserve project identity and distinguish AI description from review.
