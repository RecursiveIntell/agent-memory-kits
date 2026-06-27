# Semantic Memory for Codex

Local-first persistent memory for Codex, backed by `semantic-memory-mcp`.

This plugin provides:

- lean/standard/full `sm_*` MCP tool profiles through `.mcp.json` and optional global Codex config
- Codex skills for recall, capture, curation, graph exploration, repo sync, conversation memory, setup repair, and memory-keeper workflows
- global/project Codex hooks for session priming, project-scoped recall, warm HTTP gated prompt recall, adaptive routing, and capture nudging
- automatic background codebase ingestion for complex prompts in non-trivial git repos when `code:<repo>` memory is missing
- a plugin-bundled hook manifest for forward-compatible plugin hook discovery
- a deterministic codebase ingester that writes facts plus dependency graph edges
- doctor, read-only audit, and recall-eval scripts for setup and retrieval quality checks

## Setup

```bash
/home/sikmindz/plugins/semantic-memory/scripts/setup.sh
codex plugin add semantic-memory@personal
/home/sikmindz/plugins/semantic-memory/scripts/doctor.py
/home/sikmindz/plugins/semantic-memory/scripts/eval_recall.py
```

Fresh Codex sessions load the plugin. `scripts/setup.sh` also merges the global MCP server, read-only tool approvals, built-in memories coordination, `memory_keeper` subagent role, and global hooks so the memory system works in fresh Codex homes and outside the plugin path on this machine.

## Hooks

Global hooks are installed at `~/.codex/hooks.json`:

- `SessionStart`: injects memory status and project-scoped recall for real git repos
- `UserPromptSubmit`: searches memory over the warm HTTP server when available, falls back to stdio, and injects only gated relevant facts
- `PreCompact`: reminds the agent before manual/auto compaction when supported
- `Stop`: end-of-turn fallback reminder to persist durable verified facts

The MCP server gives agent clients concise server-wide instructions during initialization. The MCP search tools and recall hooks filter facts targeted by `supersedes` graph edges whenever a non-superseded alternative is available, while explicit stale/history queries can still inspect old facts. The recall hook also requires meaningful lexical overlap after generic coding-agent terms are removed, which keeps broad prompts from injecting unrelated codebase facts.

The Codex recall hook now follows the Hermes/Claude kit retrieval split:

- simple lookup: scoped warm `/search`, then broad `/search`, then plain `sm_search` fallback
- relationship, contradiction, synthesis, or temporal prompts: scoped warm `/search-routed` first, then broad `/search-routed` or `/search`, then stdio `sm_search`
- warm results use relative RRF score gating via `SM_RECALL_SCOREREL`; stdio results use cosine band/floor gating
- scoped hits are ranked ahead of broad hits, with a small freshness preference for current facts

The plugin keeps both `PreCompact` and `Stop` capture nudges. `PreCompact` gives Claude-style timing on Codex builds that support it; `Stop` remains the reliable fallback. The plugin also includes `hooks/hooks.json` for Codex builds that discover plugin-bundled hooks.

The `codebase-auto-ingest.py` prompt hook uses the same routing classifier to reduce bug risk on complex codebase work. For relationship, contradiction, synthesis, temporal, implementation, fix, debug, or review prompts, it checks the current git repo. If the repo is large enough and the `code:<repo>` namespace has no useful coverage, it starts `scripts/ingest_codebase.py --dedupe` in the background. The prompt is never blocked; lock and stamp files under `~/.cache/semantic-memory/auto-ingest` prevent repeated runs.

## Tool Surface

Read/search tools include `sm_stats`, `sm_search`, `sm_search_with_routing`, `sm_get_fact`, `sm_list_facts`, `sm_list_namespaces`, and `sm_get_fact_neighbors`. Exact availability depends on `SEMANTIC_MEMORY_TOOL_PROFILE` (`lean`, `standard`, or `full`).

Graph, supersession, and lifecycle tools include `sm_add_graph_edge`, `sm_list_graph_edges`, `sm_invalidate_graph_edge`, `sm_graph_path`, `sm_supersede_fact`, `sm_discord_search`, `sm_community`, `sm_topology`, `sm_factor_graph`, `sm_decoder_analyze`, `sm_run_lifecycle`, and `sm_set_provenance`.

Conversation tools: `sm_create_session`, `sm_add_message`, `sm_list_sessions`, `sm_get_messages`, `sm_search_conversations`.

Write tools: `sm_add_fact`, `sm_supersede_fact`, `sm_ingest_document`, conversation writes, graph writes, provenance, lifecycle, and edge invalidation should continue to prompt unless the user chooses more automation.

Hard-delete tools: `sm_delete_fact` and `sm_delete_namespace` are irreversible forget operations. They are intentionally not included in read-only auto-approval and should be used only when the user explicitly asks to delete memory rather than supersede or lower confidence.

## Skills

- `semantic-memory`: standard recall, verification, and persistence protocol.
- `memory-capture`: disciplined durable fact writes with dedupe and optional graph links.
- `memory-curator`: read-only audit, then approval-gated reconciliation.
- `knowledge-graph-explorer`: graph traversal, paths, communities, and optional HTML graph views.
- `memory-sync` and `memory-ingest-codebase`: deterministic repository ingestion and refresh.
- `memory-conversation-log`: search and manage conversation-memory sessions.
- `memory-keeper` and `memory-subagent-workflow`: heavy memory work and subagent delegation patterns.
- `memory-setup-doctor`: install and health checks for fresh Codex instances.

## Ingest Or Sync A Repo

```bash
python3 /home/sikmindz/plugins/semantic-memory/scripts/ingest_codebase.py --path /path/to/repo --dry-run
python3 /home/sikmindz/plugins/semantic-memory/scripts/ingest_codebase.py --path /path/to/repo --dedupe
```

The ingester is deterministic: it reads manifests, language stats, top-level layout, and README context, then writes facts and graph edges through the local MCP server.

## Maintenance Scripts

- `scripts/install-global-config.py`: idempotently merges global MCP config, read-only approvals, memories coordination, and the `memory_keeper` agent role.
- `scripts/audit_memory.py`: read-only store audit covering stats, namespace counts, graph topology/community, sessions, and retrieval checks.
- `scripts/doctor.py`: setup health check for plugin install state, config, hooks, approvals, MCP reachability, tool surface, and cache cleanliness.
- `scripts/eval_recall.py`: focused recall and hook-gating evaluation.

## Codex Memories Coordination

Codex's built-in file-based memories can complement semantic-memory. This setup keeps semantic-memory as the explicit source-aware recall layer and configures built-in memories to avoid learning from turns polluted by MCP or web-search context.

## Runtime Knobs

- `SEMANTIC_MEMORY_HTTP_PORT`: Codex warm HTTP sidecar port, default `1739`; Hermes/Claude may use `1738`
- `SEMANTIC_MEMORY_HTTP_URL`: explicit warm HTTP URL for hooks, default `http://127.0.0.1:$SEMANTIC_MEMORY_HTTP_PORT`
- `SEMANTIC_MEMORY_TOOL_PROFILE`: `lean`, `standard`, or `full`, default `lean`
- `SEMANTIC_MEMORY_LLM_MODEL`: optional local LLM model for server-side routing and AI features
- `SM_RECALL_SCOREREL`: relative warm-score gate, default `0.5`
- `SM_AUTO_INGEST`: enable automatic background codebase ingestion, default `1`
- `SM_AUTO_INGEST_MIN_FILES`: tracked-file threshold, default `120`
- `SM_AUTO_INGEST_MIN_MANIFESTS`: manifest threshold, default `2`
- `SM_AUTO_INGEST_TTL_SECONDS`: minimum time before retrying an unchanged repo, default `86400`
- `SM_AUTO_INGEST_MAX_COMPONENTS`: maximum component facts per automatic ingest, default `400`
- `SM_AUTO_INGEST_STATE_DIR`: override lock/stamp/log directory
