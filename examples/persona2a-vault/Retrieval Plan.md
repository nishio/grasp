---
id: demo-retrieval-plan
title: Retrieval Plan
tags: [demo, retrieval]
---
# Retrieval Plan

Question: what should an agent read before changing the ingestion pipeline?

Start with `search "ingestion pipeline" --context 1` to find candidate lines. Then use `read "Ingestion Pipeline"` so the agent sees backlinks, related pages, and unresolved targets.

The expected reading set is [[Ingestion Pipeline]], [[Context Budget]], [[Source Provenance]], and [[Stale Write Guard]].

If the answer only cites a line hit and ignores [[Agent Memory]], it has not used the graph.
