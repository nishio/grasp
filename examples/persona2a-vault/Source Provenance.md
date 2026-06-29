---
id: demo-source-provenance
title: Source Provenance
aliases:
  - Evidence Trail
tags: [provenance, source]
---
# Source Provenance

Source provenance is the discipline of keeping evidence separate from current claims.

The current claim lives in pages such as [[Context Budget]] and [[Ingestion Pipeline]]. The evidence lives in source-backed pages such as [[HN Reddit Digest]].

When an agent writes [[Agent Memory]], it should preserve the source trail and avoid turning old log entries into current facts.

This is why [[Stale Write Guard]] matters: a clean projection is part of the evidence chain.
