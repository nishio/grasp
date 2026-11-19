---
type: entity
summary: grasp images scans materialized Gyazo references and maintains a resumable sidecar cache without changing source notes.
sources:
  - grasp/gyazo.py
  - grasp/cli.py
  - tests/test_gyazo.py
  - https://gyazo.com/api/docs/image
---
# gyazo-local-media

## Implemented contract

`grasp --store library.sqlite --project notes --json images scan` enumerates canonical 32-hex Gyazo IDs from materialized lines. It stores project, page ID/title, line ID/index and observed URL in `<store>.assets/index.sqlite`. The note store, schema and note events are unchanged; an old source schema is refused instead of recovered automatically. A partial local graph remains partial: this command does not hydrate missing pages.

`images fetch --reuse-dir /path/to/images --local-only` first reuses files whose stem is exactly the image ID. Multiple directories are allowed. Supported PNG/JPEG/GIF/WebP signatures are checked, HTML/SVG rejected, bytes capped at 25 MiB, and content hashes recorded. A reused image may be a previous derivative; the local source path is preserved as provenance and original resolution is not promised.

`images fetch --limit 20 --timeout 4` downloads bounded batches. `--limit` bounds network image attempts, not local reuse; each image may require oEmbed plus the image request. Default is 50 attempts, 5 seconds per request. `--page-id` / repeatable `--image-id` scope work. Failed items are skipped unless `--retry-failed`; pending and failed are distinct. On rerun, valid saved files are skipped and missing/corrupt files can be restored. Completed files and statuses survive interruption; a currently interrupted attempt may remain pending and is retried on the next run.

Downloads use observed direct image URLs or official Gyazo oEmbed. Only HTTPS Gyazo/API/image hosts, including redirects, are allowed. No cookies or access tokens are requested. Timeout, HTTP failure and invalid responses are recorded per image, allowing the batch to continue. There is no retry loop or background schedule. File replacement is atomic; stored names contain the ID and hash. Existing source copies are not moved or overwritten.

`images list --page-id ID --limit 50 --offset 0` returns status, local path, MIME, hash, source and references. `images status` returns counts. Counted saved rows are metadata; list detects missing local files and fetch verifies hashes. The sidecar belongs to one absolute source-store path. Backup/migration tools do not yet move or rebind it automatically.

## UI boundary

The desktop consumer delegates scan, fetch, paths and status to grasp. It should serve only returned saved images through a constrained local mechanism and show failures as placeholders. Rendering must not implicitly fetch remote images. Source notes remain read-only unless an existing explicit authoring workflow permits changes.

## Validation

Fixture tests cover shared references/deduplication, offline reuse, idempotence, corruption repair, bounded requests, page scoping, 503 then recovery, HTML rejection and unsafe URLs. Every fixture compares the source SQLite bytes before and after. These tests do not assert availability of the live service.

## Open Questions

Authenticated/private images, unsupported media and video, redirects to other future official hosts, cache migration/eviction, full image decoding, and continuously changed source graphs remain outside this increment. There is no bulk auto-download on app startup.

Related: [[grasp-v1-implemented]], [[grasp-backlog]].
