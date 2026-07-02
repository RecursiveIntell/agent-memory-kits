#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
check() { echo "==> $*"; "$@" || fail=1; }

for f in $(find shared cursor windsurf cline roo-code continue opencode codex claude hermes -type f -name '*.sh' 2>/dev/null); do
  check bash -n "$f"
done

for f in $(find shared cursor windsurf cline roo-code continue opencode codex claude hermes -type f -name '*.py' 2>/dev/null); do
  check python3 -m py_compile "$f"
done

for f in \
  cursor/mcp.json.example \
  windsurf/mcp_config.json.example \
  cline/mcp_settings.json.example \
  roo-code/mcp_settings.json.example \
  continue/config.json.example \
  opencode/opencode.json.example \
  shared/snippets/mcp-stdio.json \
  codex/.agents/plugins/marketplace.json \
  codex/plugins/semantic-memory/.codex-plugin/plugin.json \
  claude/.claude-plugin/marketplace.json \
  claude/plugins/semantic-memory/.claude-plugin/plugin.json \
  hermes/plugin.json; do
  [ -f "$f" ] && check python3 -m json.tool "$f" >/dev/null
done

if command -v claude >/dev/null 2>&1; then
  check claude plugin validate claude
  check claude plugin validate claude/plugins/semantic-memory
fi

check python3 cursor/scripts/doctor.py

if [ "$fail" -eq 0 ]; then
  echo "ALL KIT VALIDATION PASSED"
else
  echo "KIT VALIDATION FAILED" >&2
fi
exit "$fail"
