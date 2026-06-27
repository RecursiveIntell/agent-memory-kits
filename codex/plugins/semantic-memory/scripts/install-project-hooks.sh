#!/usr/bin/env bash
# Install semantic-memory hooks into a single repository's .codex/hooks.json.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${1:-$(pwd)}"
HOOKS_JSON="$REPO/.codex/hooks.json"
mkdir -p "$(dirname "$HOOKS_JSON")"

CODEX_HOME="$REPO/.codex" "$ROOT/scripts/install-global-hooks.sh"
