# semantic-memory for OpenCode

This is the OpenCode MCP setup kit for semantic-memory-mcp.

Capability boundary:
- Works: exposes the `sm_*` semantic-memory MCP tools to OpenCode once the MCP config is registered.
- Works: local-first memory storage, hybrid search, graph tools, provenance, supersession, claims, and manual/codebase-ingest workflows.
- Not claimed yet: automatic pre-prompt recall or project primer. This package is MCP-first unless a stable OpenCode hook/context-injection API is verified and implemented later.

## Install

From the repository root:

```bash
opencode/scripts/setup.sh
```

Copy the printed `mcpServers.semantic-memory` snippet into OpenCode MCP server configuration.

## Verify

```bash
opencode/scripts/doctor.py
```

Expected:
- `opencode.json.example` parses as JSON.
- `semantic-memory-mcp` binary is found.
- memory dir exists.
- MCP `tools/list` exposes `sm_search`, `sm_add_fact`, `sm_stats`, and `sm_supersede_fact`.

## Use inside OpenCode

Ask OpenCode to call the semantic-memory MCP tools, for example:

```text
Search semantic memory for facts about this repository before changing code.
```

or:

```text
Save this decision to semantic memory with namespace code:<repo-name> and source OpenCode.
```

## Notes

If the warm HTTP health check warns, MCP stdio can still work. Warm HTTP is mainly for hook-based hosts; MCP tool use does not require it.
