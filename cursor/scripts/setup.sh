#!/usr/bin/env bash
# Setup helper for Cursor. Writes no config unless --write-project is passed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="$($ROOT/shared/scripts/install_semantic_memory_mcp.sh)"
CG_BIN="$($ROOT/shared/scripts/install_context_governor.sh || true)"
mkdir -p "${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"
RUNNER="$ROOT/cursor/scripts/run-server.sh"

cat <<EOF
semantic-memory-mcp: $BIN
runner:              $RUNNER

Cursor MCP config snippet:
{
  "mcpServers": {
    "semantic-memory": {
      "command": "$RUNNER",
      "env": {
        "SEMANTIC_MEMORY_DIR": "${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}",
        "SEMANTIC_MEMORY_TOOL_PROFILE": "lean",
        "SEMANTIC_MEMORY_HTTP_PORT": "1739"
      }
    }
  }
}
EOF

if [ "${1:-}" = "--write-project" ]; then
  mkdir -p .cursor
  if [ -e .cursor/mcp.json ]; then
    cp .cursor/mcp.json ".cursor/mcp.json.bak.$(date +%Y%m%d%H%M%S)"
  fi
  cat > .cursor/mcp.json <<EOF
{
  "mcpServers": {
    "semantic-memory": {
      "command": "$RUNNER",
      "env": {
        "SEMANTIC_MEMORY_DIR": "${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}",
        "SEMANTIC_MEMORY_TOOL_PROFILE": "lean",
        "SEMANTIC_MEMORY_HTTP_PORT": "1739"
      }
    }
  }
}
EOF
  echo "wrote .cursor/mcp.json"
else
  echo
  echo "To write project-local config, run: cursor/scripts/setup.sh --write-project"
  echo "For global Cursor config, copy the snippet into your Cursor MCP settings per the current Cursor docs."
fi
cat <<EOF

Context-injection setup (workspace rules):
  $ROOT/shared/scripts/install-context-rules.py cursor --scope workspace --workspace /path/to/project

Cursor global User Rules are UI-managed; use the workspace rule command above.
EOF

echo "Context Governor MCP companion:"
echo "  command: $ROOT/shared/scripts/context-governor-mcp.py"
echo "  store:   ${CONTEXT_GOVERNOR_STORE:-$HOME/.local/share/context-governor/receipts}"
