#!/usr/bin/env bash
# Host-agnostic semantic-memory-mcp launcher for agent MCP configs.
set -uo pipefail

SM_BIN="${SEMANTIC_MEMORY_MCP_BIN:-}"
[ -z "$SM_BIN" ] && [ -x "$HOME/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp" ] && SM_BIN="$HOME/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp"
[ -z "$SM_BIN" ] && [ -x "$HOME/.local/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.local/bin/semantic-memory-mcp"
[ -z "$SM_BIN" ] && SM_BIN="$(command -v semantic-memory-mcp 2>/dev/null || true)"
[ -z "$SM_BIN" ] && [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.cargo/bin/semantic-memory-mcp"

if [ -z "$SM_BIN" ] || [ ! -x "$SM_BIN" ]; then
  echo "semantic-memory-mcp not found. Install it with: cargo install semantic-memory-mcp" >&2
  echo "Or run this kit's scripts/setup.sh first." >&2
  exit 127
fi

SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"
mkdir -p "$SM_DIR" 2>/dev/null || true
SM_EMBEDDER="${SEMANTIC_MEMORY_EMBEDDER:-candle}"
SM_HTTP_PORT="${SEMANTIC_MEMORY_HTTP_PORT:-1739}"
SM_TOOL_PROFILE="${SEMANTIC_MEMORY_TOOL_PROFILE:-lean}"
SM_LLM_MODEL="${SEMANTIC_MEMORY_LLM_MODEL:-${LLM_MODEL:-granite4.1:3b}}"
SM_TURBO_QUANT="${SEMANTIC_MEMORY_TURBO_QUANT:-${SM_TURBO_QUANT:-0}}"

EXTRA_ARGS=()
HELP="$("$SM_BIN" --help 2>&1 || true)"
case "$HELP" in *"--tool-profile"*) [ -n "$SM_TOOL_PROFILE" ] && EXTRA_ARGS+=(--tool-profile "$SM_TOOL_PROFILE") ;; esac
case "$HELP" in *"--http-port"*) [ -n "$SM_HTTP_PORT" ] && [ "$SM_HTTP_PORT" != "0" ] && EXTRA_ARGS+=(--http-port "$SM_HTTP_PORT") ;; esac
case "$HELP" in *"--llm-model"*) [ -n "$SM_LLM_MODEL" ] && EXTRA_ARGS+=(--llm-model "$SM_LLM_MODEL") ;; esac
if [ "$SM_TURBO_QUANT" = "1" ] || [ "$SM_TURBO_QUANT" = "true" ]; then
  case "$HELP" in *"--turbo-quant"*) EXTRA_ARGS+=(--turbo-quant) ;; esac
fi

if [ -n "$SM_EMBEDDER" ]; then
  exec "$SM_BIN" --memory-dir "$SM_DIR" --embedder "$SM_EMBEDDER" "${EXTRA_ARGS[@]}" "$@"
fi
exec "$SM_BIN" --memory-dir "$SM_DIR" "${EXTRA_ARGS[@]}" "$@"
