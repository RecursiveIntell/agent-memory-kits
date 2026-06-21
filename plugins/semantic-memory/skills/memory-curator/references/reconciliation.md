# Reconciliation playbook (memory-curator)

Detailed procedures for Phase 2. Load this only when actually reconciling.

## Duplicates

1. Among the duplicate set, choose the **canonical** fact: the clearest, most complete, best-attributed phrasing.
2. If the duplicates carry information the canonical one lacks, write ONE merged superseding fact (append) capturing the union, then point the old ones at it.
3. Link non-canonical facts to the canonical with an entity edge `relation: "duplicate_of"` (or `"superseded_by"`). This preserves history while making the canonical fact the hub.
4. Do **not** invalidate the underlying facts — they remain for audit. Retrieval naturally favors the richer canonical fact.

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

- `sm_run_lifecycle` flags items safe to forget/compress. The store is append-only, so "forgetting" here means: lower provenance, mark superseded, or (for true noise) note it for the user — never silent destructive deletion.
- Always get explicit user sign-off before treating anything as forgettable.
