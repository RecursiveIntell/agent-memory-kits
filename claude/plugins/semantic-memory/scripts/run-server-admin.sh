#!/usr/bin/env bash
# Start semantic-memory-mcp with the full/admin tool profile for maintenance tasks.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SEMANTIC_MEMORY_TOOL_PROFILE="${SEMANTIC_MEMORY_ADMIN_TOOL_PROFILE:-full}"
# Admin stdio servers should not compete with the daily warm HTTP sidecar port.
export SEMANTIC_MEMORY_HTTP_PORT="${SEMANTIC_MEMORY_ADMIN_HTTP_PORT:-0}"
exec "$SCRIPT_DIR/run-server.sh" "$@"
