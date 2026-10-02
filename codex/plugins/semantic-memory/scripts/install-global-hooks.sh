#!/usr/bin/env bash
# Install fallback semantic-memory hooks into a Codex hooks layer.
#
# Plugin-bundled hooks/hooks.json is the primary source on current Codex builds.
# Use this fallback only for a host that does not discover plugin-bundled hooks.
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


def add(event: str, relative_script: str, status: str, timeout: int, matcher: str | None = None) -> None:
    command = f"PYTHONDONTWRITEBYTECODE=1 python3 {root / relative_script}"
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
            if existing_command == command or existing_command.endswith(f"/{relative_script}"):
                hook["command"] = command
                hook["timeout"] = timeout
                hook["statusMessage"] = status
                if matcher:
                    existing["matcher"] = matcher
                return
    groups.append(group)


def remove_obsolete(existing: str) -> bool:
    """Remove known registrations from pre-plugin-bundled hook versions."""
    return (
        "context-compact-reminder.py" in existing
        or "/hooks/context-governor-compact.py" in existing
        or "/plugins/cache/personal/" in existing
    )


for event, groups in list(hooks.items()):
    if not isinstance(groups, list):
        continue
    kept = []
    for group in groups:
        if not isinstance(group, dict):
            kept.append(group)
            continue
        group_hooks = group.get("hooks")
        if not isinstance(group_hooks, list):
            kept.append(group)
            continue
        remaining = [
            hook for hook in group_hooks
            if not remove_obsolete(str(hook.get("command") or ""))
        ]
        if remaining:
            group["hooks"] = remaining
            kept.append(group)
    hooks[event] = kept


add("SessionStart", "hooks/memory-primer.py", "Priming semantic memory", 12, "startup|resume|clear")
add("UserPromptSubmit", "hooks/memory-recall.py", "Recalling semantic memory", 12)
add("UserPromptSubmit", "hooks/codebase-auto-ingest.py", "Checking codebase memory", 5)
# PreCompact is the closest Claude parity hook on Codex builds that support it;
# Stop remains a reliable fallback and end-of-turn nudge.
add("PreCompact", "hooks/memory-capture-nudge.py", "Checking semantic-memory capture", 5, "manual|auto")
add("PreCompact", "scripts/context-governor-compact.py", "Context Governor compaction", 30, "manual|auto")
add("Stop", "hooks/memory-capture-nudge.py", "Checking semantic-memory capture", 5)

target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"semantic-memory global hooks installed: {target}")
PY
