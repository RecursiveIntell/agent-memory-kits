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

Pick the right tool for each case:

- **Stale fact with a correct replacement** → `sm_supersede_fact(old_fact_id, content, namespace, reason)`: writes the corrected fact, links it, and marks the old one superseded so **search filters it automatically**. This is the DEFAULT for "outdated, here's the current truth" — keeps history, no clutter in recall.
- **Two near-duplicate facts** → `sm_supersede_fact(old_id, content=merged_content, reason="consolidated duplicates")`: merges their content into a replacement fact and links the old fact with a "supersedes" edge. Cleaner than delete+re-add and preserves audit trail.
- **Stale/outdated fact** → `sm_supersede_fact(old_id, content=new_content, reason="...")`: creates a replacement with audit edge. Always prefer supersede over in-place modification — it keeps history searchable.
- **Pure noise / error, no replacement** → `sm_delete_fact(fact_id)`: HARD, irreversible removal. Use only when a fact is simply wrong/junk and should vanish entirely.
- **Bad ingest or obsolete namespace** → `sm_delete_namespace(namespace)`: removes all of it (facts/docs/chunks/sessions). Confirm contents first with `sm_list_namespaces` + `sm_list_facts`.
- **Contradictions** → supersede the losing side (or write a reconciliation fact linking both); `sm_invalidate_graph_edge` any edge asserting the wrong relation.
- **Confidence / gaps** → `sm_set_provenance` on verified facts; `sm_add_graph_edge` to connect related-but-unlinked facts.
- **Reconciliation helpers** → `sm_reconcile` (check store consistency, find orphaned/missing entries), `sm_vacuum` (reclaim space from deleted/superseded items), `sm_reembed_all` (re-embed all facts after model upgrade or corruption; check first with `sm_embeddings_are_dirty`), `sm_get_search_receipt` (fetch the full result set + routing decisions of a prior search for audit trails).

Discipline: **prefer `sm_supersede_fact`** (keeps history, auto-filters from search) over hard delete; reserve `sm_delete_*` for true noise or bad ingests. Every destructive op requires explicit user approval. Report exactly what changed (ids + reasons).

## Guardrails
- Never delete; the store evolves by append, supersession, and edge invalidation.
- Never let memory outrank current artifacts — if a fact conflicts with a live repo/spec, the artifact wins.
- Batch related changes and keep reasons in the receipts.
