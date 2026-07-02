# semantic-memory for Windsurf

This is the Windsurf MCP setup kit for semantic-memory-mcp.

Capability boundary:
- Works: exposes the `sm_*` semantic-memory MCP tools to Windsurf once the MCP config is registered.
- Works: local-first memory storage, hybrid search, graph tools, provenance, supersession, claims, and manual/codebase-ingest workflows.
- Works: context-injection via host rule/instruction files. The setup kit can install a semantic-memory rule that tells the agent to retrieve memory through MCP, or through the shared context command when shell execution is available.
- Boundary: this is rule/instruction based for this host, not a guaranteed pre-prompt hook unless the host exposes a stable hook API.

## Install

From the repository root:

```bash
windsurf/scripts/setup.sh
```

Copy the printed `mcpServers.semantic-memory` snippet into Windsurf Cascade MCP settings.

## Verify

```bash
windsurf/scripts/doctor.py
```

Expected:
- `mcp_config.json.example` parses as JSON.
- `semantic-memory-mcp` binary is found.
- memory dir exists.
- MCP `tools/list` exposes `sm_search`, `sm_add_fact`, `sm_stats`, and `sm_supersede_fact`.

## Use inside Windsurf

Ask Windsurf to call the semantic-memory MCP tools, for example:

```text
Search semantic memory for facts about this repository before changing code.
```

or:

```text
Save this decision to semantic memory with namespace code:<repo-name> and source Windsurf.
```

## Notes

If the warm HTTP health check warns, MCP stdio can still work. Warm HTTP is mainly for hook-based hosts; MCP tool use does not require it.


## Context injection

Install a workspace rule into a project:

```bash
shared/scripts/install-context-rules.py windsurf --scope workspace --workspace /path/to/project
```

Install a global rule where the host has a documented global-rule location:

```bash
shared/scripts/install-context-rules.py windsurf --scope global
```

The installed rule points at:

```bash
shared/scripts/semantic-memory-context.py --prompt "$USER_TASK"
```

That command queries the warm HTTP server first (`SEMANTIC_MEMORY_HTTP_PORT`, default `1739`) and falls back to stdio MCP. Returned entries are explicitly marked as recall, not ground truth.


## Context compaction / receipts

This kit also includes Context Governor as a companion MCP server and rule layer.

- MCP server: `shared/scripts/context-governor-mcp.py`
- Receipt-backed compact command: `shared/scripts/context-governor-compact.py`
- Rule text: `shared/rules/context-governor.md`

Use it when a Windsurf session is long, a handoff is needed, or context is about to be compacted. It preserves high-risk context and stores exact fallback receipts that can be searched and expanded later.

Boundary: for hosts without a verified pre-compact hook, this is rule/command/MCP assisted. It does not claim automatic transcript capture unless the host exposes transcript messages to an extension/hook API.


## Quick install

Print config snippets only:

```bash
windsurf/scripts/setup.sh
```

Write project-local rule/config files:

```bash
windsurf/scripts/setup.sh --write-project /path/to/project
```

Write safe user/global rule files where this host supports them:

```bash
windsurf/scripts/setup.sh --write-user
```

Dry run before writing:

```bash
windsurf/scripts/setup.sh --dry-run --write-project /path/to/project
```

Verify:

```bash
windsurf/scripts/doctor.py
shared/scripts/doctor-all.py --deep
```
