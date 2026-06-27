---
name: memory-curator
description: Audit and improve the semantic memory store. Use when the user asks to review, clean, audit, prune, maintain, reconcile, find duplicates or contradictions, inspect stale facts, or check memory health. Produces a read-only report first, then only changes memory after approval.
---

# Memory Curator

Keep the store healthy as it grows. Audit first, present a report, then reconcile only after approval. Never destructively delete.

## Phase 1: Audit

Run and summarize:

1. `sm_stats`: fact, document, chunk, graph edge, database, and embedding health.
2. `sm_list_namespaces`, then `sm_list_facts(namespace, limit, offset)`: enumerate namespaces exhaustively. Use `sm_get_fact` for full inspection.
3. `sm_community`: community structure and local contradiction scan.
4. `sm_run_lifecycle`: syndromes, subtraction candidates, recompression need, and quantization assessment.
5. `sm_topology`: connected components, cycles, structural voids, and suggested missing links.
6. `sm_search_with_routing` or `sm_decoder_analyze`: ranking or contradiction diagnostics when needed, when exposed by the active tool profile.

For a repeatable first pass, run `scripts/audit_memory.py` from the plugin root. It is read-only and summarizes stats, namespace counts, graph/community health, sessions, and retrieval checks.

Present a concise health report: store size, duplicates, contradictions, stale or forgettable items, graph gaps, and recommended actions. Stop for approval before writing.

Read [references/reconciliation.md](references/reconciliation.md) when actually reconciling.

## Phase 2: Reconcile

After approval:

- Duplicates: keep or write the best canonical fact, then link old facts with `duplicate_of`; use `sm_supersede_fact` when a new merged canonical fact replaces stale duplicates.
- Contradictions: use `sm_supersede_fact` for the winning verified correction, link it with `reconciles` when useful, and invalidate wrong edges with `sm_invalidate_graph_edge`.
- Confidence: use `sm_set_provenance` for verified facts.
- Gaps: add real `sm_add_graph_edge` connections for verified missing context.

Report exact fact ids, edge ids, and reasons.

## Guardrails

Current artifacts outrank memory. Never fabricate graph structure just to improve topology metrics. Never silently delete.
