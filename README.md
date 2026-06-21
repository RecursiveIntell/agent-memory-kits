# semantic-memory-claude-kit

Give Claude Code a **persistent, local-first semantic memory** — and the tools to
fill it. Two pieces:

1. **`semantic-memory` plugin** — wires the [`semantic-memory-mcp`](https://github.com/RecursiveIntell/semantic-memory-mcp)
   server into Claude Code with three hooks:
   - **Auto-recall** (`UserPromptSubmit`): every prompt is embedded and searched
     against your memory; the most relevant facts are injected as context.
   - **Session primer** (`SessionStart`): each session starts knowing the store
     exists, its size, and the recall/persist/discipline protocol.
   - **Capture nudge** (`PreCompact`): before context is compacted, Claude is
     reminded to persist durable facts (model-driven — nothing is auto-written).
2. **`ingest_codebase.py`** — a **language-agnostic** ingester that turns any
   repository into memory: facts for the repo and each component, plus a
   `belongs_to` / `depends_on` dependency graph. Parses Cargo, npm, Python, Go,
   Maven, .NET, and Composer manifests; detects Gradle/Ruby/Dart/Elixir/CMake/
   Swift; and always captures language stats, layout, and README.

## Prerequisites

- **Rust toolchain** (for the one-time `cargo install semantic-memory-mcp`).
- **`jq`** and **`python3`** (used by the hooks and ingester).
- Everything runs locally — no API keys, no cloud. The embedding model
  (`nomic-embed-text-v1.5`, ~550 MB) downloads once from HuggingFace and is cached.

## Install (plugin — recommended)

```
/plugin marketplace add RecursiveIntell/semantic-memory-claude-kit
/plugin install semantic-memory
/memory-setup        # installs the binary + allowlists tools, one time
```

`/memory-setup` handles the binary install and permission allowlist. The MCP
server and hooks come from the plugin automatically.

## Install (manual — no plugins)

```
git clone https://github.com/RecursiveIntell/semantic-memory-claude-kit
./semantic-memory-claude-kit/install.sh
```

This installs the binary, registers the MCP server at user scope, allowlists the
`sm_*` tools, and merges the three hooks into `~/.claude/settings.json`
(non-destructively). Restart Claude Code afterward.

## Ingest a codebase

```
/memory-ingest /path/to/any/repo          # in Claude Code
# or directly:
python3 plugins/semantic-memory/scripts/ingest_codebase.py --path /path/to/repo --dry-run
```

## Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `SEMANTIC_MEMORY_DIR` | `~/.local/share/semantic-memory` | Where the store lives |
| `SEMANTIC_MEMORY_MCP_BIN` | auto-resolved | Override the binary path |
| `SEMANTIC_MEMORY_HOOK_DEBUG` | unset | If set to a file path, hooks log each firing there |
| `SM_RECALL_MINTOP` / `SM_RECALL_BAND` / `SM_RECALL_ABSFLOOR` | 0.58 / 0.12 / 0.54 | Tune recall precision |

## Notes

- Hooks **fail open**: any error or missing binary exits cleanly and never blocks
  a prompt.
- Recall uses a **relative** similarity gate (nomic embeddings sit ~0.5 even for
  unrelated text), so unrelated prompts inject nothing.
- The ingester **never deletes** memory; re-running appends. Use a distinct
  `--namespace` per project (defaults to `code:<repo-slug>`).

License: Apache-2.0
