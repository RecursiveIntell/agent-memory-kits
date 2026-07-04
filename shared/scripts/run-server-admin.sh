#!/usr/bin/env bash
# Start semantic-memory-mcp with the full/admin tool profile for maintenance tasks.
# Emits admin-preflight intent before starting and postflight receipt after.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SEMANTIC_MEMORY_TOOL_PROFILE="${SEMANTIC_MEMORY_ADMIN_TOOL_PROFILE:-full}"
# Admin stdio servers should not compete with the daily warm HTTP sidecar port.
export SEMANTIC_MEMORY_HTTP_PORT="${SEMANTIC_MEMORY_ADMIN_HTTP_PORT:-0}"

# Emit admin preflight intent (fail open — does not block server start)
python3 "$SCRIPT_DIR/admin-preflight.py" preflight \
  --operation reembed_missing \
  --target "${SEMANTIC_MEMORY_DIR:-default}" \
  --operator "${USER:-unknown}" \
  --confirm 2>/dev/null || true

# Run the admin server
"$SCRIPT_DIR/run-server.sh" "$@"
ADMIN_EXIT=$?

# Emit admin postflight receipt (fail open)
python3 "$SCRIPT_DIR/admin-preflight.py" postflight \
  --operation reembed_missing \
  --target "${SEMANTIC_MEMORY_DIR:-default}" \
  --exit-code "$ADMIN_EXIT" \
  --duration-secs 0 2>/dev/null || true

exit $ADMIN_EXIT
