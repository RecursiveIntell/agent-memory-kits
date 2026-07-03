#!/usr/bin/env bash
# Resolve the semantic-memory-mcp binary + memory dir, then exec the stdio server.
# Portable: works regardless of where the binary was installed.
#
# The server is launched with --http-port so it ALSO co-hosts a warm HTTP
# endpoint alongside stdio MCP. The shell hooks (recall/primer) query that warm
# process over HTTP instead of cold-spawning a fresh binary on every prompt —
# the embedder (nomic) stays loaded, so hook latency drops from ~seconds to ~ms.
# Bind is fail-open: if the port is already taken (another session, or another
# warm server), the HTTP thread just exits and stdio MCP keeps serving normally.
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

# Embedder backend: candle (default, in-process CPU), ollama (external GPU), or
# mock. Override with SEMANTIC_MEMORY_EMBEDDER (and SEMANTIC_MEMORY_* embedding
# vars, which the binary reads directly) to use a faster GPU backend.
SM_EMBEDDER="${SEMANTIC_MEMORY_EMBEDDER:-candle}"

# Warm HTTP port — must match _resolve.sh (default 1739). Change it if another
# service already owns the port. Set to 0 or empty to disable the warm endpoint
# and fall back to cold-spawn hooks.
SM_HTTP_PORT="${SEMANTIC_MEMORY_HTTP_PORT:-1739}"

# Tool profile: lean (33 daily-use tools), standard (39 + maintenance/audit),
# full (48, all tools including import/projection). Default lean for best
# agent tool-selection accuracy (optimal is 15-25 tools).
SM_TOOL_PROFILE="${SEMANTIC_MEMORY_TOOL_PROFILE:-lean}"

if [ -n "$SM_HTTP_PORT" ] && [ "$SM_HTTP_PORT" != "0" ]; then
  if [ "$SM_TURBO_QUANT" = "1" ] || [ "$SM_TURBO_QUANT" = "true" ]; then
  case "$("$SM_BIN" --help 2>&1)" in *"--turbo-quant"*) EXTRA+=(--turbo-quant) ;; esac
fi
exec "$SM_BIN" --memory-dir "$SM_DIR" --embedder "$SM_EMBEDDER" --http-port "$SM_HTTP_PORT" --tool-profile "$SM_TOOL_PROFILE" "$@"
else
  if [ "$SM_TURBO_QUANT" = "1" ] || [ "$SM_TURBO_QUANT" = "true" ]; then
  case "$("$SM_BIN" --help 2>&1)" in *"--turbo-quant"*) EXTRA+=(--turbo-quant) ;; esac
fi
exec "$SM_BIN" --memory-dir "$SM_DIR" --embedder "$SM_EMBEDDER" --tool-profile "$SM_TOOL_PROFILE" "$@"
fi
