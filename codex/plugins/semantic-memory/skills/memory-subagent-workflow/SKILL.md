---
name: memory-subagent-workflow
description: Use Codex subagents with semantic-memory for large repo exploration, memory audits, ingestion planning, graph traversal, conversation recall, and parallel recall while preserving verification discipline. Prefer memory-keeper for heavy memory-only work.
---

# Memory Subagent Workflow

Use this skill when the work is large enough to benefit from parallel exploration or independent validation of memory results. For a memory-specialist workflow, use `memory-keeper`.

## Workflow

1. Search memory in the main agent first to define the likely namespaces and prior context.
2. Give subagents narrow, verifiable tasks:
   - inspect a repo area before ingestion
   - compare memory claims against current files
   - identify duplicate or stale facts
   - propose graph relationships for a subsystem
   - enumerate namespaces or conversation sessions
3. Ask subagents to return evidence: file paths, commands run, memory fact IDs when available, and uncertainty.
4. The main agent verifies key claims before writing memory.
5. Persist only durable outcomes with `sm_add_fact`, `sm_set_provenance`, or graph tools.

## Guardrails

Do not let subagent summaries become authority. Treat them like memory: useful recall that needs verification against current artifacts. Avoid spawning subagents for small tasks where the coordination cost is higher than direct inspection.
