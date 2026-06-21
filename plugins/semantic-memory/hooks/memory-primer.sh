#!/usr/bin/env bash
# SessionStart hook — prime the session with semantic-memory status + protocol.
# FAILS OPEN: any error -> exit 0, no output.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_resolve.sh"
sm_resolve || exit 0
sm_debug "SessionStart primer fired"

init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"primer-hook","version":"1"}}}'
note='{"jsonrpc":"2.0","method":"notifications/initialized"}'
req='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"sm_stats","arguments":{}}}'

out="$(printf '%s\n%s\n%s\n' "$init" "$note" "$req" | timeout 8 "$SM_BIN" --memory-dir "$SM_DIR" 2>/dev/null)" || exit 0

stats="$(printf '%s' "$out" | python3 -c '
import sys, json
res=None
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except Exception: continue
    if o.get("id")==2:
        try: res=json.loads(o["result"]["content"][0]["text"])
        except Exception: res=None
if not res or not res.get("ok"): sys.exit(0)
print("{} facts, {} docs, {} chunks, {} graph edges".format(
    res.get("facts",0), res.get("documents",0), res.get("chunks",0), res.get("graph_edges",0)))
' 2>/dev/null)" || exit 0

[ -z "$stats" ] && exit 0

text="Persistent semantic memory is ACTIVE (semantic-memory MCP server): ${stats}. This is your primary long-term memory across all projects.
- RECALL: relevant entries are auto-injected per prompt; also call sm_search yourself before relying on conversation context alone for anything you may have stored.
- PERSIST: when you learn a durable, verified fact, store it with sm_add_fact under a namespace. Search first to avoid duplicates.
- DISCIPLINE: never let stored memory outrank current artifacts/repos. Record corrections by append/supersede, not destructive rewrite."

jq -nc --arg c "$text" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
exit 0
