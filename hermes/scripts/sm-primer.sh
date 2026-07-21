#!/usr/bin/env bash
# Hermes on_session_start hook. Fail-open semantic-memory primer.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/hooks/sm-primer.py" "$@" || true
