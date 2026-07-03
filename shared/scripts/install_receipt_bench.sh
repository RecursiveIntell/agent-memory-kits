#!/usr/bin/env bash
set -euo pipefail
if [ -x "$HOME/.local/bin/sm-bench" ]; then echo "$HOME/.local/bin/sm-bench"; exit 0; fi
if command -v sm-bench >/dev/null 2>&1; then command -v sm-bench; exit 0; fi
CRATE="${RECEIPT_BENCH_CRATE:-$HOME/Coding/Libraries/receipt-bench}"
if [ -f "$CRATE/Cargo.toml" ]; then
  cargo build --release --features sm-adapter --bin sm-bench --manifest-path "$CRATE/Cargo.toml" 2>/dev/null || true
fi
# check workspace target
if [ -x "$HOME/Coding/Libraries/target/release/sm-bench" ]; then
  mkdir -p "$HOME/.local/bin"; install -m 0755 "$HOME/Coding/Libraries/target/release/sm-bench" "$HOME/.local/bin/sm-bench"; echo "$HOME/.local/bin/sm-bench"; exit 0
fi
if [ -x "$CRATE/target/release/sm-bench" ]; then
  mkdir -p "$HOME/.local/bin"; install -m 0755 "$CRATE/target/release/sm-bench" "$HOME/.local/bin/sm-bench"; echo "$HOME/.local/bin/sm-bench"; exit 0
fi
echo "sm-bench not found. Build receipt-bench with: cargo build --features sm-adapter --bin sm-bench" >&2
exit 1
