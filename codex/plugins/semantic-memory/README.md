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

- `SessionStart`: injects memory status and project-scoped witnessed recall for real git repos
- `UserPromptSubmit`: performs mandatory witnessed stdio retrieval and injects only provenance-complete facts through the inert data-only envelope
- `PreCompact`: reminds the agent before manual/auto compaction when supported
- `Stop`: end-of-turn fallback reminder to persist durable verified facts

The MCP server gives agent clients concise server-wide instructions during initialization. Prompt hooks reject superseded facts rather than widening back to stale input, require witnessed retrieval receipts, and require meaningful lexical overlap after generic coding-agent terms are removed.

The Codex recall hook uses mandatory `sm_search_witnessed` retrieval. Inside a Git repository it queries the collision-safe namespace first, consults the legacy basename alias only when the primary namespace has no admissible hits, and never widens to unscoped recall. Outside a repository it may use declared thematic or broad witnessed passes. Only identity-, provenance-, state-, trust-, and receipt-complete entries can reach the shared escaped-JSON `DATA ONLY — NOT AN INSTRUCTION` framing compiler.

The plugin keeps both `PreCompact` and `Stop` capture nudges. `PreCompact` gives Claude-style timing on Codex builds that support it; `Stop` remains the reliable fallback. The plugin also includes `hooks/hooks.json` for Codex builds that discover plugin-bundled hooks.

The `codebase-auto-ingest.py` prompt hook is disabled unless `SM_AUTO_INGEST` is explicitly enabled. When enabled for complex codebase prompts, it checks only the collision-safe `code:<repo>-<path-digest>` namespace for coverage before starting `scripts/ingest_codebase.py --dedupe` in the background. Lock and stamp files under `~/.cache/semantic-memory/auto-ingest` prevent repeated runs.

## Tool Surface

The default `lean`/`standard` profile exposes witnessed retrieval, stored replay, and assertion/action authority decisions. `agent` adds bounded read-only fact, graph, namespace, conversation, receipt, and statistics access. Exact availability is defined by the MCP server profile manifest (`stable`, `lean`, `standard`, `agent`, or `full`).

Prompt hooks use `sm_search_witnessed`; they do not rely on raw search, maintenance, or mutation tools. The explicit `full` operator profile can advertise broader graph, lifecycle, conversation, and mutation descriptors, but the hardened MCP composition rejects canonical writes and forgetting unless a trusted authenticated authority issuer is injected.

`sm_delete_fact` and `sm_delete_namespace` therefore fail closed in the current composition. Corrections remain append-plus-supersession operations, not destructive truth rewrites.

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
- `SM_AUTO_INGEST`: explicitly enable automatic background codebase ingestion, default `0` (off)
- `SM_AUTO_INGEST_MIN_FILES`: tracked-file threshold, default `120`
- `SM_AUTO_INGEST_MIN_MANIFESTS`: manifest threshold, default `2`
- `SM_AUTO_INGEST_TTL_SECONDS`: minimum time before retrying an unchanged repo, default `86400`
- `SM_AUTO_INGEST_MAX_COMPONENTS`: maximum component facts per automatic ingest, default `400`
- `SM_AUTO_INGEST_STATE_DIR`: override lock/stamp/log directory
