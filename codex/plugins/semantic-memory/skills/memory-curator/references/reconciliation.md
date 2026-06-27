# Reconciliation Playbook

Load this only when moving from audit to approved reconciliation.

## Duplicates

1. Choose the canonical fact: clearest, most complete, best-attributed phrasing.
2. If duplicate facts each carry useful information, write one merged superseding fact with `sm_supersede_fact` for the first stale source, then add `duplicate_of` or additional `supersedes` edges for the remaining sources.
3. Link non-canonical facts to the canonical with `duplicate_of`; reserve `supersedes` for verified stale replacements.
4. Do not invalidate underlying facts only because they are duplicates; preserve audit history.

## Contradictions

1. Confirm it is a real contradiction, not a time- or scope-specific difference.
2. Verify against current artifacts. Current artifacts outrank memory.
3. Use `sm_supersede_fact` to write a reconciliation fact: "X was believed; Y supersedes it because Z as of DATE."
4. Link the reconciliation fact to both originals with `reconciles` when that relationship will be useful later.
5. Use `sm_invalidate_graph_edge` for stored edges that assert a now-wrong relationship.

## Provenance

Use `sm_set_provenance` with calibrated confidence and support count. Keep confidence lower for inferred or unreviewed claims.

## Graph Gaps

For each `MissingContext` or `MissingLink` from `sm_topology`, add an edge only when a genuine relation exists. Re-run `sm_topology` after approved changes.

## Forgetting

`sm_run_lifecycle` flags candidates to forget or compress. Because memory is append-first, forgetting means lowering provenance, marking stale facts with `sm_supersede_fact`, or reporting noise for user sign-off.
