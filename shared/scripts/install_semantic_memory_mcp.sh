#!/usr/bin/env bash
# Install or locate semantic-memory-mcp for public agent kits.
set -euo pipefail

if [ -n "${SEMANTIC_MEMORY_MCP_BIN:-}" ] && [ -x "$SEMANTIC_MEMORY_MCP_BIN" ]; then
  echo "$SEMANTIC_MEMORY_MCP_BIN"
  exit 0
fi

for candidate in \
  "$HOME/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp" \
  "$HOME/.local/bin/semantic-memory-mcp" \
  "$(command -v semantic-memory-mcp 2>/dev/null || true)" \
  "$HOME/.cargo/bin/semantic-memory-mcp"; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    echo "$candidate"
    exit 0
  fi
done

command -v cargo >/dev/null 2>&1 || {
  echo "ERROR: cargo not found. Install Rust first: https://rustup.rs" >&2
  exit 1
}

echo "Installing semantic-memory-mcp with cargo..." >&2
cargo install semantic-memory-mcp
BIN="$HOME/.cargo/bin/semantic-memory-mcp"
[ -x "$BIN" ] || { echo "ERROR: install finished but $BIN is not executable" >&2; exit 1; }
echo "$BIN"
