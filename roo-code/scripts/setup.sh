#!/usr/bin/env bash
# Setup helper for Roo Code. Supports --write-project [path], --write-user, and --dry-run.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$ROOT/shared/scripts/setup-host.py" roo-code "$@"
