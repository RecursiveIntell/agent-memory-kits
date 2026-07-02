#!/usr/bin/env bash
# Setup helper for OpenCode. Writes no host config automatically; prints a current MCP snippet.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="$($ROOT/shared/scripts/install_semantic_memory_mcp.sh)"
mkdir -p "${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"
RUNNER="$ROOT/opencode/scripts/run-server.sh"
cat <<EOF
semantic-memory-mcp: $BIN
runner:              $RUNNER

OpenCode MCP config snippet:
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

echo
echo "Copy the snippet into OpenCode MCP server configuration per the current OpenCode docs."
echo "Then run: opencode/scripts/doctor.py"
