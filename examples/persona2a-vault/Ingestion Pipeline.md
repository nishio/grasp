---
id: demo-ingestion-pipeline
title: Ingestion Pipeline
aliases:
  - Markdown Importer
tags: [markdown, importer]
---
# Ingestion Pipeline

Before changing the ingestion pipeline, read [[Context Budget]], [[Source Provenance]], and [[Stale Write Guard]].

The importer should preserve frontmatter `id`, `title`, `aliases`, and `tags` because those fields keep identity separate from filenames.

The pipeline currently treats `Log.md` as a log artifact and `source/` as source-backed evidence. It should not let navigation or log pages dominate [[Related Pages]].

Risk: a naive [[Frontmatter Normalizer]] could erase aliases that make old links resolve after a rename.
