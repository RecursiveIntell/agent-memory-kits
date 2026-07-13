"""Regression coverage for Claude plugin durable-store runtime defaults."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "claude/plugins/semantic-memory"
RUNTIME_FILES = (
    PLUGIN / ".mcp.json",
    PLUGIN / "scripts/run-server.sh",
    PLUGIN / "hooks/_resolve.sh",
    PLUGIN / "scripts/context-governor-compact.py",
    PLUGIN / "scripts/context-governor-mcp.py",
    PLUGIN / "scripts/ingest_codebase.py",
)
# Benchmark outputs intentionally do not appear here: they are artifacts, not
# active durable-store runtime defaults.
LEGACY_DURABLE_DEFAULTS = (
    ".local/share/semantic-memory",
    ".local/share/context-governor/receipts",
)


def test_claude_runtime_defaults_use_canonical_durable_stores():
    mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
    servers = mcp["mcpServers"]

    assert servers["semantic-memory"]["env"]["SEMANTIC_MEMORY_DIR"] == "${HOME}/.hermes/semantic-memory.db"
    assert servers["semantic-memory-admin"]["env"]["SEMANTIC_MEMORY_DIR"] == "${HOME}/.hermes/semantic-memory.db"
    assert servers["context-governor"]["env"]["CONTEXT_GOVERNOR_STORE"] == "${HOME}/.hermes/context-governor"

    active_runtime = "\n".join(path.read_text(encoding="utf-8") for path in RUNTIME_FILES)
    assert "$HOME/.hermes/semantic-memory.db" in active_runtime
    assert '.hermes" / "context-governor"' in active_runtime or ".hermes/context-governor" in active_runtime
    launcher = (PLUGIN / "scripts/run-server.sh").read_text(encoding="utf-8")
    assert 'mkdir -p "$(dirname "$SM_DIR")"' in launcher
    assert 'mkdir -p "$SM_DIR"' not in launcher
    for legacy in LEGACY_DURABLE_DEFAULTS:
        assert legacy not in active_runtime
