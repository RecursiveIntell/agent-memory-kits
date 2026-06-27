#!/usr/bin/env bash
# One-time setup and verification for the Codex Semantic Memory plugin.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"

echo "==> semantic-memory setup for Codex"

if [ -x "$HOME/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp" ]; then
  BIN="$HOME/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp"
elif [ -x "$HOME/.local/bin/semantic-memory-mcp" ]; then
  BIN="$HOME/.local/bin/semantic-memory-mcp"
elif command -v semantic-memory-mcp >/dev/null 2>&1; then
  BIN="$(command -v semantic-memory-mcp)"
elif [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ]; then
  BIN="$HOME/.cargo/bin/semantic-memory-mcp"
else
  command -v cargo >/dev/null 2>&1 || {
    echo "ERROR: cargo not found. Install Rust first: https://rustup.rs" >&2
    exit 1
  }
  echo "    installing semantic-memory-mcp via cargo"
  cargo install semantic-memory-mcp
  BIN="$HOME/.cargo/bin/semantic-memory-mcp"
fi

mkdir -p "$SM_DIR"
echo "    binary: $BIN"
echo "    memory dir: $SM_DIR"

python3 "$ROOT/scripts/install-global-config.py"

echo "==> done"
echo "Install or refresh the plugin with: codex plugin add semantic-memory@personal"
echo "Start a new Codex thread after install so the sm_* tools and skill are loaded."
echo "Run a full health check with: $ROOT/scripts/doctor.py"
