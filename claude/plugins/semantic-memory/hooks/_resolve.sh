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
  SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.hermes/semantic-memory.db}"
  # Warm HTTP endpoint. The MCP server (run-server.sh) co-hosts a warm HTTP
  # server on this port so hooks query the already-loaded embedder instead of
  # cold-spawning a new process (which reloads the nomic model every time).
  # Default 1740. Override with SEMANTIC_MEMORY_HTTP_PORT if a host-owned warm server
  # already owns this port; keep it in sync with run-server.sh.
  SM_HTTP_PORT="${SEMANTIC_MEMORY_HTTP_PORT:-1740}"
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

# sm_record_outcome: POST /record-outcome for RL routing feedback. Silent, fail-open.
sm_record_outcome() { # $1=query, $2=outcome (good/bad), $3=query_class
  [ -n "${SM_HTTP:-}" ] || return 0
  local query="$1" outcome="$2" qclass="$3"
  local body
  body="$(jq -nc --arg q "$query" --arg o "$outcome" --arg c "$qclass" '{query:$q,outcome:$o,query_class:$c}' 2>/dev/null)" || return 0
  curl -fsS -m 2 -X POST "${SM_HTTP}/record-outcome" \
    -H 'content-type: application/json' -d "$body" >/dev/null 2>&1 || true
}
