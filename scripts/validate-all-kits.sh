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

check python3 - <<'PY'
import json
import subprocess
reqs = [
    {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"validate-all-kits","version":"1"}}},
    {"jsonrpc":"2.0","method":"notifications/initialized"},
    {"jsonrpc":"2.0","id":2,"method":"tools/list"},
]
proc = subprocess.run(
    ["shared/scripts/context-governor-mcp.py"],
    input="\n".join(json.dumps(x) for x in reqs) + "\n",
    text=True,
    capture_output=True,
    timeout=15,
    check=False,
)
if proc.returncode != 0:
    raise SystemExit(proc.stderr or f"context-governor MCP exited {proc.returncode}")
messages = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
tools = []
for msg in messages:
    if msg.get("id") == 2:
        tools = [tool.get("name") for tool in msg.get("result", {}).get("tools", [])]
required = {"cg_list_receipts", "cg_search", "cg_expand", "cg_diff_receipt"}
missing = sorted(required - set(tools))
if missing:
    raise SystemExit(f"context-governor MCP missing tools: {missing}")
print(f"context-governor MCP tools/list: {len(tools)} tools exposed")
PY

if [ "$fail" -eq 0 ]; then
  echo "ALL KIT VALIDATION PASSED"
else
  echo "KIT VALIDATION FAILED" >&2
fi
exit "$fail"
