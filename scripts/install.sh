#!/usr/bin/env bash
# Unified installer for agent-memory-kits.
# Runs all shared install scripts, then a deep doctor check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED="$ROOT/shared/scripts"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   agent-memory-kits — Unified Installer                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo

declare -A RESULTS

run_step() {
  local label="$1"
  local script="$2"
  echo "▶ Installing $label ..."
  if bash "$script" > /tmp/agent-memory-kits-install-"$label".log 2>&1; then
    local bin_path
    bin_path=$(tail -1 /tmp/agent-memory-kits-install-"$label".log)
    RESULTS["$label"]="$bin_path"
    echo "  ✓ $label → $bin_path"
  else
    RESULTS["$label"]="FAILED"
    echo "  ✗ $label failed (see /tmp/agent-memory-kits-install-$label.log)"
  fi
  echo
}

run_step "semantic-memory-mcp" "$SHARED/install_semantic_memory_mcp.sh"
run_step "context-governor"    "$SHARED/install_context_governor.sh"
run_step "claim-ledger"        "$SHARED/install_claim_ledger.sh"
run_step "receipt-bench"       "$SHARED/install_receipt_bench.sh"

echo "▶ Running deep doctor check ..."
echo
python3 "$SHARED/doctor-all.py" --deep || true
echo

# Collect the doctor-all receipt path
RECEIPT_DIR="${HOME}/.local/share/semantic-memory-agent-kits/receipts"
LATEST_RECEIPT=""
if [ -d "$RECEIPT_DIR" ]; then
  LATEST_RECEIPT=$(ls -t "$RECEIPT_DIR"/doctor-all-*.json 2>/dev/null | head -1)
fi

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Installation Summary                                     ║"
echo "╠════════════════════════════════════════════════════════════╣"
for label in "semantic-memory-mcp" "context-governor" "claim-ledger" "receipt-bench"; do
  printf "║  %-22s %s\n" "$label" "${RESULTS[$label]:-skipped}"
done
echo "╠════════════════════════════════════════════════════════════╣"
if [ -n "$LATEST_RECEIPT" ]; then
  printf "║  %-22s %s\n" "doctor receipt" "$LATEST_RECEIPT"
else
  printf "║  %-22s %s\n" "doctor receipt" "(not found)"
fi
echo "╚════════════════════════════════════════════════════════════╝"