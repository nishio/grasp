---
id: demo-context-budget
title: Context Budget
aliases:
  - Bounded Read
tags: [retrieval, agent-memory]
---
# Context Budget

A context budget is a hard limit on what the agent reads before answering or editing.

Raw search returns isolated lines. A bounded graph read returns the page, line-level backlinks, related pages, and unresolved targets in one bundle.

For this vault, an agent changing the [[Ingestion Pipeline]] should read [[Source Provenance]] and [[Stale Write Guard]] before touching code.

[[Retrieval Plan]] uses this page as the seed because it explains why a dense Markdown wiki needs graph context instead of another note-search pane.

Open question: should [[Frontmatter Normalizer]] be handled by the importer or by a later cleanup pass?
