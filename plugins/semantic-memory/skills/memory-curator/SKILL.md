---
name: memory-curator
description: Audit and improve the semantic memory store. Use when the user asks to review, clean, audit, prune, or maintain memory, to find duplicates or contradictions, to check memory health, or to reconcile conflicting facts. Produces a health report (stats, contradictions, forgettable items, graph gaps), then — only with approval — reconciles via append/supersede and edge invalidation. Never destructively deletes.
---

# Memory curator

Keep the store healthy as it grows. Audit first, present a report, then reconcile **only after the user approves** — always by append/supersede, never hard deletion.

## Phase 1 — Audit (read-only)

Run and summarize:

1. `sm_stats` — size, fact/chunk/document/edge counts, embedding model.
2. `sm_list_namespaces` then `sm_list_facts(namespace, …)` — **exhaustively enumerate** each namespace. This is how you actually find duplicates and near-duplicates (similarity search alone misses them); scan the listed content for repeats, contradictions, and stale entries. Use `sm_get_fact(id)` to inspect any candidate in full.
3. `sm_community` (resolution 1.0) with any known `contradictions` — community structure + **within-community contradiction scan**.
4. `sm_run_lifecycle` on a representative set of `item_ids` — syndromes, **subtraction candidates** (safe to forget/compress), recompression need, quantization assessment.
5. `sm_topology` — Betti numbers + structural **voids** (weakly-connected facts, missing links) and the tool's suggested connections.

Present a concise **health report**: store size, suspected duplicates/contradictions, stale/forgettable items, and graph gaps. Recommend specific actions. **Stop and ask for approval before changing anything.**

→ See [references/reconciliation.md](references/reconciliation.md) for the detailed playbook.

## Phase 2 — Reconcile (only after approval)

- **Duplicates:** keep the best-phrased fact; write a brief superseding fact noting consolidation if needed; link the others with a `supersedes`/`duplicate_of` edge. Do not hard-delete.
- **Contradictions:** write a reconciliation fact that resolves the conflict (state which holds and why), link it to both originals, and `sm_invalidate_graph_edge` any edge that asserts the wrong relation (with a clear reason).
- **Confidence:** set `sm_set_provenance` on facts you've verified (confidence + support_count).
- **Gaps:** add the suggested `sm_add_graph_edge` connections for weakly-connected but related facts.

Report exactly what changed (ids + reasons). Everything is append-only and auditable.

## Guardrails
- Never delete; the store evolves by append, supersession, and edge invalidation.
- Never let memory outrank current artifacts — if a fact conflicts with a live repo/spec, the artifact wins.
- Batch related changes and keep reasons in the receipts.
