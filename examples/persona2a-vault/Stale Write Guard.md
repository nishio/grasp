---
id: demo-stale-write-guard
title: Stale Write Guard
aliases:
  - Write Guard
tags: [write, safety]
---
# Stale Write Guard

A stale write guard stops the agent from treating a generated Markdown projection as if it were the authority.

For this demo, the source vault remains Markdown during import. The write loop copies the vault to a temp directory, appends to [[Log]], and checks `write-status --strict`.

The guard matters for [[Agent Memory]] because duplicated or stale project memory is worse than no memory.

If a direct Markdown patch happens, use [[Reconcile Markdown]] before claiming the store is clean.
