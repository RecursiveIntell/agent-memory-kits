#!/usr/bin/env bash
# Shared resolver sourced by the memory hooks. Sets SM_BIN and SM_DIR, or
# returns non-zero so the caller can exit 0 (fail-open) when memory is absent.
# Optional: set SEMANTIC_MEMORY_HOOK_DEBUG=/path/to/log to record hook firings.
sm_resolve() {
  SM_BIN="${SEMANTIC_MEMORY_MCP_BIN:-}"
  [ -z "$SM_BIN" ] && SM_BIN="$(command -v semantic-memory-mcp 2>/dev/null || true)"
  [ -z "$SM_BIN" ] && [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.cargo/bin/semantic-memory-mcp"
  [ -z "$SM_BIN" ] && [ -x "$HOME/.local/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.local/bin/semantic-memory-mcp"
  SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"
  [ -n "$SM_BIN" ] && [ -x "$SM_BIN" ] || return 1
  command -v jq >/dev/null 2>&1 || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  return 0
}
sm_debug() { # $1 = event label
  [ -n "${SEMANTIC_MEMORY_HOOK_DEBUG:-}" ] || return 0
  { printf '%s %s\n' "$(date -Iseconds 2>/dev/null || date)" "$1"; } >> "$SEMANTIC_MEMORY_HOOK_DEBUG" 2>/dev/null || true
}
