# Reconciliation playbook (memory-curator)

Detailed procedures for Phase 2. Load this only when actually reconciling.

## Duplicates

1. Among the duplicate set, choose the **canonical** fact: the clearest, most complete, best-attributed phrasing.
2. If one fact is simply an outdated version of another, `sm_supersede_fact(old_id, content, namespace, reason)` — it writes the corrected/canonical version, links it, and marks the old one superseded so **search filters it automatically**. This is the clean default.
3. If several near-identical facts collapse into one consolidated fact, write the consolidated fact, then `sm_delete_fact` the obsolete duplicates (they carry no unique history worth keeping). Reserve delete for genuine redundancy/noise.
4. For duplicates worth keeping as history, instead link non-canonical ones to the canonical with an entity edge `relation: "duplicate_of"` and leave them in place.

## Contradictions

1. Confirm it's a real contradiction (not two facts that are both true in different scopes/times — bitemporal truth allows both).
2. Determine which holds now, and the evidence grade of each. Check current artifacts — they outrank stored memory.
3. Write a **reconciliation fact**: "X was believed; Y supersedes it because Z (as of DATE)." Namespace it with the originals.
4. Link the reconciliation fact to both originals (`relation: "reconciles"`), and to the winning side (`relation: "supersedes"`).
5. `sm_invalidate_graph_edge` any stored edge that asserts the now-wrong relationship, with `reason` naming the reconciliation.

## Provenance

- For facts you have independently verified this session, `sm_set_provenance` with a calibrated `confidence` (e.g. 0.95+ for directly-checked, lower for inferred) and a `support_count` of independent observations.
- Provenance feeds the confidence semiring and downstream belief propagation; don't inflate it.

## Graph gaps (from sm_topology)

- For each `MissingContext` void (degree-1 fact), add the suggested edge if the relationship is real.
- For `MissingLink` voids (same component, no short path), add a connecting edge only when a genuine relation exists — do not fabricate structure to satisfy the metric.
- Re-run `sm_topology` afterward to confirm components dropped / voids closed.

## Forgetting (subtraction candidates)

- `sm_run_lifecycle` flags items safe to forget/compress. Hard delete now exists, so forgetting can be real:
  - **Outdated but has a replacement** → `sm_supersede_fact` (preferred — keeps history, auto-filters from search).
  - **True noise / error, no replacement** → `sm_delete_fact(fact_id)` — irreversible.
  - **A whole bad ingest or obsolete namespace** → `sm_delete_namespace(namespace)` (confirm contents with `sm_list_facts` first).
- Always get **explicit user sign-off** before any hard delete. Default to supersede; delete only when a fact should genuinely vanish.
