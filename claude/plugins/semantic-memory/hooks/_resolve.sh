#!/usr/bin/env bash
# Shared resolver sourced by the memory hooks. Sets SM_BIN, SM_DIR, and the warm
# HTTP endpoint (SM_HTTP), or returns non-zero so the caller can exit 0 (fail-open)
# when memory is absent.
# Optional: set SEMANTIC_MEMORY_HOOK_DEBUG=/path/to/log to record hook firings.
sm_resolve() {
  SM_PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  SM_BIN="${SEMANTIC_MEMORY_MCP_BIN:-}"
  [ -z "$SM_BIN" ] && SM_BIN="$(command -v semantic-memory-mcp 2>/dev/null || true)"
  [ -z "$SM_BIN" ] && [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.cargo/bin/semantic-memory-mcp"
  [ -z "$SM_BIN" ] && [ -x "$HOME/.local/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.local/bin/semantic-memory-mcp"
  SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.hermes/semantic-memory.db}"
# Optional warm HTTP endpoint retained for host integrations. Hooks themselves
# use witnessed stdio retrieval because ordinary HTTP /search lacks admission
# receipts. Set a nonzero port only when a host-owned authenticated sidecar is
# intentionally configured.
  SM_HTTP_PORT="${SEMANTIC_MEMORY_HTTP_PORT:-0}"
  SM_HTTP="${SEMANTIC_MEMORY_HTTP_URL:-http://127.0.0.1:${SM_HTTP_PORT}}"
  if [ -z "${SEMANTIC_MEMORY_KIT_SHARED:-}" ] && [ -f "$HOME/Coding/agent-memory-kits/shared/scripts/injection_framing.py" ]; then
    SEMANTIC_MEMORY_KIT_SHARED="$HOME/Coding/agent-memory-kits/shared/scripts"
  fi
  export SEMANTIC_MEMORY_KIT_SHARED
  [ -n "$SM_BIN" ] && [ -x "$SM_BIN" ] || return 1
  command -v jq >/dev/null 2>&1 || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  return 0
}
# Resolve Bearer token for token-gated warm HTTP. Never log the value. The
# canonical auth-token-file variable is checked first; legacy names remain
# supported for compatibility with older host configurations.
sm_http_token() {
  local raw=""
  if [ -n "${SEMANTIC_MEMORY_HTTP_AUTH_TOKEN_FILE:-}" ] && [ -f "$SEMANTIC_MEMORY_HTTP_AUTH_TOKEN_FILE" ]; then
    raw="$(tr -d '\r' < "$SEMANTIC_MEMORY_HTTP_AUTH_TOKEN_FILE" | head -n 1)"
  elif [ -n "${SEMANTIC_MEMORY_HTTP_TOKEN:-}" ]; then
    raw="$SEMANTIC_MEMORY_HTTP_TOKEN"
  elif [ -n "${SEMANTIC_MEMORY_HTTP_TOKEN_FILE:-}" ] && [ -f "$SEMANTIC_MEMORY_HTTP_TOKEN_FILE" ]; then
    raw="$(tr -d '\r' < "$SEMANTIC_MEMORY_HTTP_TOKEN_FILE" | head -n 1)"
  else
    return 1
  fi
  raw="${raw#"${raw%%[![:space:]]*}"}"
  raw="${raw%"${raw##*[![:space:]]}"}"
  [ -n "$raw" ] || return 1
  case "$raw" in *[[:space:]]*) return 1 ;; esac
  printf '%s' "$raw"
}

# Run one read-only MCP tool call over stdio using the canonical launcher. This
# keeps hooks on the witnessed MCP path and prevents them from starting HTTP
# listeners or bypassing launcher validation.
sm_stdio_rpc() { # $1 = tool name, $2 = JSON arguments
  local tool="${1:-}" args="${2:-}" init note req out
  [ -n "$tool" ] || return 1
  [ -n "$args" ] || args='{}'
  init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"claude-semantic-memory-hook","version":"1"}}}'
  note='{"jsonrpc":"2.0","method":"notifications/initialized"}'
  req="$(jq -nc --arg tool "$tool" --argjson args "$args" '{jsonrpc:"2.0",id:2,method:"tools/call",params:{name:$tool,arguments:$args}}')" || return 1
  out="$(printf '%s\n%s\n%s\n' "$init" "$note" "$req" |
    SEMANTIC_MEMORY_MCP_BIN="$SM_BIN" \
    SEMANTIC_MEMORY_DIR="$SM_DIR" \
    SEMANTIC_MEMORY_HTTP_PORT=0 \
    SEMANTIC_MEMORY_MCP_HTTP_PORT=0 \
    SEMANTIC_MEMORY_TOOL_PROFILE="${SEMANTIC_MEMORY_TOOL_PROFILE:-agent}" \
    timeout 10 "$SM_PLUGIN_ROOT/scripts/run-server.sh" 2>/dev/null)" || return 1
  printf '%s' "$out" | python3 -c '
import json, sys
for line in sys.stdin:
    try:
        obj = json.loads(line)
    except Exception:
        continue
    if obj.get("id") == 2:
        try:
            print(obj["result"]["content"][0]["text"])
        except Exception:
            pass
' 2>/dev/null
}
# curl wrapper: attach Authorization when a token resolves.
sm_curl() {
  local tok=""
  tok="$(sm_http_token 2>/dev/null)" || tok=""
  if [ -n "$tok" ]; then
    curl -H "Authorization: Bearer ${tok}" "$@"
  else
    curl "$@"
  fi
}
# sm_warm: returns 0 iff the warm HTTP server is reachable and healthy. Hooks
# call this to choose the fast warm path (curl) over the cold fallback (spawn
# the binary over stdio). Requires curl; without curl -> cold path.
sm_warm() {
  command -v curl >/dev/null 2>&1 || return 1
  sm_curl -fsS -m 1 "${SM_HTTP}/health" 2>/dev/null | grep -q '"ok":true' || return 1
  return 0
}
sm_debug() { # $1 = event label
  [ -n "${SEMANTIC_MEMORY_HOOK_DEBUG:-}" ] || return 0
  { printf '%s %s\n' "$(date -Iseconds 2>/dev/null || date)" "$1"; } >> "$SEMANTIC_MEMORY_HOOK_DEBUG" 2>/dev/null || true
}

# sm_classify_query: lightweight A/B/C/D/E query classification via keyword signals.
# Echoes the class letter on stdout. No args — reads query from stdin.
# A=simple, B=multi-hop, C=contradiction, D=synthesis, E=temporal.
sm_classify_query() {
  local q="$1"
  local ql
  ql="$(printf '%s' "$q" | tr '[:upper:]' '[:lower:]')"
  # C: contradiction signals
  case "$ql" in
    *contradict*|*conflict*|*disagree*|*"vs "*|*versus*|*"is it true"*|*wrong*)
      printf 'C'; return;;
  esac
  # D: synthesis signals
  case "$ql" in
    *summar*|*overview*|*"all about"*|*themes*|*landscape*|*everything*|*compar*|*compare*)
      printf 'D'; return;;
  esac
  # E: temporal signals
  case "$ql" in
    *when*|*before*|*after*|*changed*|*current*|*latest*|*updated*|*timeline*|*"how old"*)
      printf 'E'; return;;
  esac
  # B: multi-hop signals (2+ terms + relation words)
  local term_count
  term_count="$(printf '%s' "$ql" | wc -w | tr -d ' ')"
  if [ "$term_count" -ge 3 ]; then
    case "$ql" in
      *connect*|*between*|*"depends on"*|*"relates to"*|*relationship*|*"how did"*|*"how does"*|*"work with"*|*"lead to"*|*link*|*integrat*)
        printf 'B'; return;;
    esac
  fi
  printf 'A'
}
