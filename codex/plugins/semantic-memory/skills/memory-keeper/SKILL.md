---
name: memory-keeper
description: Memory specialist workflow for heavy semantic-memory work. Use for multi-step memory audits, deep graph exploration, bulk namespace recall, contradiction reconciliation, conversation recall, or when memory work should be isolated from the main task.
---

# Memory Keeper

This is the Codex-native counterpart to the Claude `memory-keeper` subagent. Use it directly, or delegate to the configured Codex `memory_keeper` role when multi-agent tools are available and the task is large. On this machine the role config lives at `/home/sikmindz/.codex/agents/memory-keeper.toml`.

## Capabilities

- Recall and browse: `sm_search`, `sm_search_with_routing`, `sm_list_namespaces`, `sm_list_facts`, `sm_get_fact`.
- Graph: `sm_get_fact_neighbors`, `sm_discord_search`, `sm_graph_path`, `sm_community`, `sm_topology`, `sm_factor_graph`.
- Curate: `sm_run_lifecycle`, `sm_set_provenance`, `sm_add_graph_edge`, `sm_invalidate_graph_edge`.
- Conversation memory: `sm_search_conversations`, `sm_list_sessions`, `sm_get_messages`, `sm_create_session`, `sm_add_message`.
- Codebase memory: `scripts/ingest_codebase.py` dry-run and dedupe sync.

## Operating Rules

1. Read ids before reasoning over them. Use `sm_get_fact` or `sm_get_fact_neighbors`.
2. Enumerate for audits. Use `sm_list_namespaces` and paginated `sm_list_facts`, not search alone.
3. Never destructively delete. Do not use `sm_delete_fact` or `sm_delete_namespace` unless the user explicitly asks to forget memory. Corrections are append/supersede with clear reasons.
4. Current artifacts outrank memory.
5. Return concise findings: relevant ids, changes made, contradictions, graph gaps, and recommended next steps.

## Delegation

If a Codex subagent is spawned, give it a narrow task and require evidence. The main agent must verify key claims before writing facts or edges.
