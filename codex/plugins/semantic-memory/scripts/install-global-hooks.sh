#!/usr/bin/env bash
# Install semantic-memory hooks into the global Codex hooks layer.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_JSON="${CODEX_HOME:-$HOME/.codex}/hooks.json"
mkdir -p "$(dirname "$HOOKS_JSON")"

python3 - "$HOOKS_JSON" "$ROOT" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

target = Path(sys.argv[1]).expanduser()
root = Path(sys.argv[2]).resolve()

try:
    data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
except Exception:
    data = {}
hooks = data.setdefault("hooks", {})


def add(event: str, script: str, status: str, timeout: int, matcher: str | None = None) -> None:
    command = f"PYTHONDONTWRITEBYTECODE=1 python3 {root / 'hooks' / script}"
    group = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": timeout,
                "statusMessage": status,
            }
        ]
    }
    if matcher:
        group["matcher"] = matcher
    groups = hooks.setdefault(event, [])
    for existing in groups:
        for hook in existing.get("hooks", []):
            existing_command = str(hook.get("command") or "")
            if existing_command == command or existing_command.endswith(f"/hooks/{script}"):
                hook["command"] = command
                hook["timeout"] = timeout
                hook["statusMessage"] = status
                if matcher:
                    existing["matcher"] = matcher
                return
    groups.append(group)


add("SessionStart", "memory-primer.py", "Priming semantic memory", 12, "startup|resume|clear")
add("UserPromptSubmit", "memory-recall.py", "Recalling semantic memory", 12)
add("UserPromptSubmit", "codebase-auto-ingest.py", "Checking codebase memory", 5)
# PreCompact is the closest Claude parity hook on Codex builds that support it;
# Stop remains a reliable fallback and end-of-turn nudge.
add("PreCompact", "memory-capture-nudge.py", "Checking semantic-memory capture", 5, "manual|auto")
add("Stop", "memory-capture-nudge.py", "Checking semantic-memory capture", 5)

target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"semantic-memory global hooks installed: {target}")
PY
