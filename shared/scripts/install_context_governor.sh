#!/usr/bin/env bash
set -euo pipefail
CRATE="${CONTEXT_GOVERNOR_CRATE:-$HOME/Coding/Libraries/context-governor}"
BIN_DIR="${HOME}/.local/bin"
if [ -x "$BIN_DIR/context-governor" ]; then
  echo "$BIN_DIR/context-governor"
  exit 0
fi
if command -v context-governor >/dev/null 2>&1; then
  command -v context-governor
  exit 0
fi
if [ -f "$CRATE/Cargo.toml" ]; then
  cargo build --release --manifest-path "$CRATE/Cargo.toml"
  mkdir -p "$BIN_DIR"
  install -m 0755 "$CRATE/target/release/context-governor" "$BIN_DIR/context-governor"
  echo "$BIN_DIR/context-governor"
  exit 0
fi
cat >&2 <<EOF
context-governor binary not found.
Set CONTEXT_GOVERNOR_BIN or CONTEXT_GOVERNOR_CRATE, or install from:
  https://github.com/RecursiveIntell/context-governor
EOF
exit 1
