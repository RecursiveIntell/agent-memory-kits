#!/usr/bin/env bash
set -euo pipefail
if [ -x "$HOME/.local/bin/claim-ledger" ]; then echo "$HOME/.local/bin/claim-ledger"; exit 0; fi
if command -v claim-ledger >/dev/null 2>&1; then command -v claim-ledger; exit 0; fi
CRATE="${CLAIM_LEDGER_CRATE:-$HOME/Coding/Libraries/claim-ledger}"
if [ -f "$CRATE/Cargo.toml" ]; then
  cargo build --release --manifest-path "$CRATE/Cargo.toml" 2>/dev/null || true
  BIN="$CRATE/target/release/claim-ledger"
  [ -f "$BIN" ] || BIN="$(dirname "$(cargo build --release --manifest-path "$CRATE/Cargo.toml" 2>&1 >/dev/null; echo "$CRATE/target/release/claim-ledger")")/claim-ledger"
  if [ -x "$BIN" ]; then mkdir -p "$HOME/.local/bin"; install -m 0755 "$BIN" "$HOME/.local/bin/claim-ledger"; echo "$HOME/.local/bin/claim-ledger"; exit 0; fi
fi
# check workspace target
if [ -x "$HOME/Coding/Libraries/target/release/claim-ledger" ]; then
  mkdir -p "$HOME/.local/bin"; install -m 0755 "$HOME/Coding/Libraries/target/release/claim-ledger" "$HOME/.local/bin/claim-ledger"; echo "$HOME/.local/bin/claim-ledger"; exit 0
fi
echo "claim-ledger not found. Install from https://github.com/RecursiveIntell/Libraries" >&2
exit 1
