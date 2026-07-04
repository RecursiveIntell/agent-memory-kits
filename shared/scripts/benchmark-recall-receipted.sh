#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/benchmark-recall.py" \
  --fixtures-dir "$SCRIPT_DIR/../fixtures" \
  --out "$SCRIPT_DIR/../_receipts/recall-benchmark-$(date +%Y%m%dT%H%M%SZ).json"