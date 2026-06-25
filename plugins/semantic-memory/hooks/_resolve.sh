#!/usr/bin/env bash
# Shared resolver sourced by the memory hooks. Sets SM_BIN, SM_DIR, and the warm
# HTTP endpoint (SM_HTTP), or returns non-zero so the caller can exit 0 (fail-open)
# when memory is absent.
# Optional: set SEMANTIC_MEMORY_HOOK_DEBUG=/path/to/log to record hook firings.
sm_resolve() {
  SM_BIN="${SEMANTIC_MEMORY_MCP_BIN:-}"
  [ -z "$SM_BIN" ] && SM_BIN="$(command -v semantic-memory-mcp 2>/dev/null || true)"
  [ -z "$SM_BIN" ] && [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.cargo/bin/semantic-memory-mcp"
  [ -z "$SM_BIN" ] && [ -x "$HOME/.local/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.local/bin/semantic-memory-mcp"
  SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"
  # Warm HTTP endpoint. The MCP server (run-server.sh) co-hosts a warm HTTP
  # server on this port so hooks query the already-loaded embedder instead of
  # cold-spawning a new process (which reloads the nomic model every time).
  # Default 1739 — deliberately NOT 1738, which a separate Hermes warm server
  # may own pointed at a different store (~/.hermes). Override with
  # SEMANTIC_MEMORY_HTTP_PORT, and keep it in sync with run-server.sh.
  SM_HTTP_PORT="${SEMANTIC_MEMORY_HTTP_PORT:-1739}"
  SM_HTTP="http://127.0.0.1:${SM_HTTP_PORT}"
  [ -n "$SM_BIN" ] && [ -x "$SM_BIN" ] || return 1
  command -v jq >/dev/null 2>&1 || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  return 0
}
# sm_warm: returns 0 iff the warm HTTP server is reachable and healthy. Hooks
# call this to choose the fast warm path (curl) over the cold fallback (spawn
# the binary over stdio). Requires curl; without curl -> cold path.
sm_warm() {
  command -v curl >/dev/null 2>&1 || return 1
  curl -fsS -m 1 "${SM_HTTP}/health" 2>/dev/null | grep -q '"ok":true' || return 1
  return 0
}
sm_debug() { # $1 = event label
  [ -n "${SEMANTIC_MEMORY_HOOK_DEBUG:-}" ] || return 0
  { printf '%s %s\n' "$(date -Iseconds 2>/dev/null || date)" "$1"; } >> "$SEMANTIC_MEMORY_HOOK_DEBUG" 2>/dev/null || true
}
