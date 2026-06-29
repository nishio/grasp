---
id: demo-agent-memory
title: Agent Memory
aliases:
  - Project Memory
tags: [agent-memory, llm-wiki]
---
# Agent Memory

Agent memory is useful only when an agent can recover the current decision and the evidence that changed it.

This demo treats memory as a graph, not as a transcript dump. A useful answer should cite [[Context Budget]], check the [[Stale Write Guard]], and keep [[Source Provenance]] close.

The file-back habit is simple: close a session by writing the durable finding, then verify the projection instead of trusting the chat.

Open question: should [[Session Handoff Template]] be a page or a generated view?
