---
name: memory-maintenance
description: Maintain semantic-memory quality for Codex by auditing duplicates, stale or contradictory facts, provenance, graph relationships, lifecycle output, topology, recall ranking, and direct namespace reads. Prefer memory-curator for full audit and reconciliation.
---

# Memory Maintenance

Use this skill when memory quality, cleanup, duplicate facts, stale context, contradictory facts, graph health, or recall ranking is part of the task. For full audit/reconciliation, use `memory-curator`; this skill remains a compact maintenance fallback.

## Workflow

1. Check store health with `sm_stats`.
2. For a repeatable read-only report, run `scripts/audit_memory.py` from the plugin root.
3. Search before changing anything:
   - `sm_search` for likely duplicates or stale facts.
   - `sm_list_namespaces` and `sm_list_facts(namespace)` for exhaustive namespace audits.
   - `sm_get_fact` and `sm_get_fact_neighbors` to hydrate ids before reasoning over them.
   - `sm_search_with_routing` for broad, temporal, or multi-hop questions when the current profile exposes it.
4. Update only verified durable facts:
   - Add concise corrections with `sm_add_fact`.
   - Use `sm_supersede_fact` when a correction replaces a verified stale fact; it writes the replacement and durable `supersedes` edge in one call.
   - Use `sm_set_provenance` when confidence, source support, or uncertainty matters.
   - Use graph tools only for durable relationships worth reusing later.
5. Use advanced tools for focused maintenance:
   - `sm_run_lifecycle` for stale or contradicted material.
   - `sm_topology`, `sm_community`, `sm_discord_search`, and `sm_factor_graph` for graph-level inspection.
   - `sm_decoder_analyze` for deeper memory diagnostics.
6. Run `python3 <plugin-root>/scripts/eval_recall.py` after changing recall thresholds, ingestion strategy, or memory contents that should affect retrieval quality.

## Judgment

Memory is recall, not authority. Verify against current files, current Git state, connected apps, or primary sources. Prefer adding a verified correction over rewriting history when the old fact explains why a previous decision was made.

Do not store secrets, guesses, private keys, raw credential logs, or personal data unless the user explicitly requests it and it is necessary.
