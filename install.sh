#!/usr/bin/env bash
# Fallback installer for users NOT using the Claude Code plugin system.
# Installs the binary, registers the MCP server at user scope, allowlists its
# tools, and wires the three hooks into ~/.claude/settings.json. Idempotent.
#
# Plugin users do NOT need this — just add the marketplace and install the
# 'semantic-memory' plugin. This script reproduces the same wiring manually.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$KIT_DIR/plugins/semantic-memory"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HOOKS_DST="$CLAUDE_DIR/hooks"
SETTINGS="$CLAUDE_DIR/settings.json"
SM_DIR="${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}"

echo "==> semantic-memory setup (manual / non-plugin)"

# 1. binary
if command -v semantic-memory-mcp >/dev/null 2>&1; then
  BIN="$(command -v semantic-memory-mcp)"
elif [ -x "$HOME/.cargo/bin/semantic-memory-mcp" ]; then
  BIN="$HOME/.cargo/bin/semantic-memory-mcp"
elif [ -x "$HOME/.local/bin/semantic-memory-mcp" ]; then
  BIN="$HOME/.local/bin/semantic-memory-mcp"
else
  echo "    installing semantic-memory-mcp via cargo…"
  command -v cargo >/dev/null 2>&1 || { echo "ERROR: cargo not found. Install Rust: https://rustup.rs"; exit 1; }
  cargo install semantic-memory-mcp
  BIN="$HOME/.cargo/bin/semantic-memory-mcp"
fi
echo "    binary: $BIN"

mkdir -p "$SM_DIR" "$HOOKS_DST"

# 2. copy hook scripts (portable)
cp "$PLUGIN/hooks/_resolve.sh" "$PLUGIN/hooks/memory-recall.sh" \
   "$PLUGIN/hooks/memory-primer.sh" "$PLUGIN/hooks/memory-capture-nudge.sh" "$HOOKS_DST/"
chmod +x "$HOOKS_DST"/memory-*.sh
echo "    hooks installed to: $HOOKS_DST"

# 3. register MCP server at user scope (if claude CLI present)
if command -v claude >/dev/null 2>&1; then
  if ! claude mcp get semantic-memory >/dev/null 2>&1; then
    claude mcp add -s user semantic-memory "$BIN" -- --memory-dir "$SM_DIR" || true
  fi
  echo "    MCP server registered (user scope)"
fi

# 4. merge settings.json: permission allowlist + hooks
python3 - "$SETTINGS" "$HOOKS_DST" <<'PY'
import json, os, sys
settings, hooks_dst = sys.argv[1], sys.argv[2]
os.makedirs(os.path.dirname(settings), exist_ok=True)
data = {}
if os.path.exists(settings):
    try: data = json.load(open(settings))
    except Exception: data = {}
perms = data.setdefault("permissions", {}).setdefault("allow", [])
if "mcp__semantic-memory" not in perms:
    perms.append("mcp__semantic-memory")
def hook(cmd, **kw):
    return {"hooks": [dict(type="command", command=os.path.join(hooks_dst, cmd), **kw)]}
hk = data.setdefault("hooks", {})
def ensure(event, entry, matcher=None):
    arr = hk.setdefault(event, [])
    cmd = entry["hooks"][0]["command"]
    for e in arr:
        for h in e.get("hooks", []):
            if h.get("command") == cmd:
                return
    if matcher: entry = {"matcher": matcher, **entry}
    arr.append(entry)
ensure("SessionStart", hook("memory-primer.sh", timeout=12), matcher="startup|resume|clear")
ensure("UserPromptSubmit", hook("memory-recall.sh", timeout=12))
ensure("PreCompact", hook("memory-capture-nudge.sh", timeout=5), matcher="manual|auto")
json.dump(data, open(settings, "w"), indent=2)
print("    settings.json merged:", settings)
PY

echo "==> done. Restart Claude Code (or open /hooks) to load the hooks."
echo "    Ingest a codebase:  python3 $PLUGIN/scripts/ingest_codebase.py --path /your/repo"
