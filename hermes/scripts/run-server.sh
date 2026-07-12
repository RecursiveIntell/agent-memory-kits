#!/usr/bin/env bash
# Resolve semantic-memory-mcp, then exec the stdio server. Optionally co-hosts
# the warm HTTP endpoint when SEMANTIC_MEMORY_HTTP_PORT is non-empty/non-zero.
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

SM_BIN="${SEMANTIC_MEMORY_MCP_BIN:-}"
[ -z "$SM_BIN" ] && [ -x "$HOME/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp" ] && SM_BIN="$HOME/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp"
[ -z "$SM_BIN" ] && [ -x "$HOME/.local/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.local/bin/semantic-memory-mcp"
[ -z "$SM_BIN" ] && SM_BIN="$(command -v semantic-memory-mcp 2>/dev/null || true)"
[ -z "$SM_BIN" ] && [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ] && SM_BIN="$HOME/.cargo/bin/semantic-memory-mcp"

if [ -z "$SM_BIN" ] || [ ! -x "$SM_BIN" ]; then
  echo "semantic-memory-mcp not found. Install it with: cargo install semantic-memory-mcp" >&2
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
HELP="$(env -u SEMANTIC_MEMORY_HTTP_TOKEN -u SM_BENCH_HTTP_AUTH_TOKEN "$SM_BIN" --help 2>&1 || true)"
HAS_TOOL_PROFILE_ARG=0
for arg in "$@"; do
  [ "$arg" = "--tool-profile" ] && HAS_TOOL_PROFILE_ARG=1
  case "$arg" in
    --http-auth-token|--http-auth-token=*)
      echo "Direct --http-auth-token is forbidden; use SEMANTIC_MEMORY_HTTP_TOKEN_FILE or SEMANTIC_MEMORY_HTTP_TOKEN." >&2
      exit 2
    ;;
  esac
done
case "$HELP" in *"--tool-profile"*) [ -n "$SM_TOOL_PROFILE" ] && [ "$HAS_TOOL_PROFILE_ARG" = "0" ] && EXTRA_ARGS+=(--tool-profile "$SM_TOOL_PROFILE") ;; esac
if [ -n "$SM_HTTP_PORT" ] && [ "$SM_HTTP_PORT" != "0" ]; then
  case "$HELP" in *"--http-port"*) ;; *)
    echo "semantic-memory-mcp does not support --http-port; set SEMANTIC_MEMORY_HTTP_PORT=0 for stdio-only operation." >&2
    exit 2
  ;; esac
  case "$HELP" in *"--http-auth-token-file"*) ;; *)
    echo "semantic-memory-mcp does not support --http-auth-token-file; upgrade it or set SEMANTIC_MEMORY_HTTP_PORT=0 for stdio-only operation." >&2
    exit 2
  ;; esac

  SM_HTTP_TOKEN="${SEMANTIC_MEMORY_HTTP_TOKEN:-}"
  if [ -n "$SM_HTTP_TOKEN" ]; then
    if ! SM_HTTP_TOKEN="$(
      PYTHONPATH="$SCRIPT_DIR/.." python3 -c '
import sys
from http_auth import normalize_http_token
token = normalize_http_token(sys.stdin.read())
if token is None:
    raise SystemExit(2)
sys.stdout.write(token)
' <<<"$SM_HTTP_TOKEN"
    )"; then
      echo "SEMANTIC_MEMORY_HTTP_TOKEN must be non-empty and contain no whitespace." >&2
      exit 2
    fi
    # Keep explicit credentials out of argv: inherit a private read-only fd.
    exec 3<<<"$SM_HTTP_TOKEN"
    SM_HTTP_TOKEN_FILE="/proc/self/fd/3"
  else
    SM_HTTP_TOKEN_FILE="${SEMANTIC_MEMORY_HTTP_TOKEN_FILE:-$HOME/.hermes/semantic-memory-http-1739.token}"
    if [ ! -r "$SM_HTTP_TOKEN_FILE" ]; then
      echo "SEMANTIC_MEMORY_HTTP_PORT=$SM_HTTP_PORT requires SEMANTIC_MEMORY_HTTP_TOKEN, SEMANTIC_MEMORY_HTTP_TOKEN_FILE, or ~/.hermes/semantic-memory-http-1739.token. Set SEMANTIC_MEMORY_HTTP_PORT=0 for stdio-only operation." >&2
      exit 2
    fi
  fi
  EXTRA_ARGS+=(--http-port "$SM_HTTP_PORT" --http-auth-token-file "$SM_HTTP_TOKEN_FILE")
fi
case "$HELP" in *"--llm-model"*) [ -n "$SM_LLM_MODEL" ] && EXTRA_ARGS+=(--llm-model "$SM_LLM_MODEL") ;; esac
if [ "$SM_TURBO_QUANT" = "1" ] || [ "$SM_TURBO_QUANT" = "true" ]; then
  case "$HELP" in *"--turbo-quant"*) EXTRA_ARGS+=(--turbo-quant) ;; esac
fi

# Never forward token values inherited from the caller into the MCP child.
unset SEMANTIC_MEMORY_HTTP_TOKEN SM_BENCH_HTTP_AUTH_TOKEN SM_HTTP_TOKEN

if [ -n "$SM_EMBEDDER" ]; then
  exec "$SM_BIN" --memory-dir "$SM_DIR" --embedder "$SM_EMBEDDER" "${EXTRA_ARGS[@]}" "$@"
fi
exec "$SM_BIN" --memory-dir "$SM_DIR" "${EXTRA_ARGS[@]}" "$@"
