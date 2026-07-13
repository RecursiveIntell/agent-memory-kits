#!/usr/bin/env bash
# Hermes post_tool_call hook: lightweight, fail-open tool/action receipts.
# Stores only compact observations when semantic-memory warm HTTP is available.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/hooks/sm-auto-edge.py" "$@" || true
