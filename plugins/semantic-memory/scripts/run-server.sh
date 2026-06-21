#!/usr/bin/env bash
# Resolve the semantic-memory-mcp binary + memory dir, then exec the stdio server.
# Portable: works regardless of where the binary was installed.
set -uo pipefail

SM_BIN="${SEMANTIC_MEMORY_MCP_BIN:-}"
[ -z "$SM_BIN" ] && SM_BIN="$(command -v semantic-memory-mcp 2>/dev/null || true)"
[ -z "$SM_BIN" ] && [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.cargo/bin/semantic-memory-mcp"
[ -z "$SM_BIN" ] && [ -x "$HOME/.local/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.local/bin/semantic-memory-mcp"

if [ -z "$SM_BIN" ] || [ ! -x "$SM_BIN" ]; then
  echo "semantic-memory-mcp not found. Install it with:  cargo install semantic-memory-mcp   (or run /memory-setup)" >&2
  exit 127
fi

SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"
mkdir -p "$SM_DIR" 2>/dev/null || true

exec "$SM_BIN" --memory-dir "$SM_DIR" "$@"
