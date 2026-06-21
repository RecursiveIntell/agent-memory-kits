#!/usr/bin/env bash
# SessionStart hook — prime the session with semantic-memory status, the recall/
# persist protocol, AND project-scoped recall: facts relevant to the current repo
# (from the hook's cwd, git-root aware) injected up front. FAILS OPEN.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_resolve.sh"
sm_resolve || exit 0
sm_debug "SessionStart primer fired"

# --- read cwd from hook stdin; derive a project name (git root preferred) ---
input="$(cat 2>/dev/null || true)"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"
[ -z "$cwd" ] && cwd="$PWD"
proj_root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
proj_name="$(basename "${proj_root:-$cwd}")"

init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"primer-hook","version":"1"}}}'
note='{"jsonrpc":"2.0","method":"notifications/initialized"}'
stats_req='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"sm_stats","arguments":{}}}'
proj_req="$(jq -nc --arg q "$proj_name codebase project overview" \
  '{jsonrpc:"2.0",id:3,method:"tools/call",params:{name:"sm_search",arguments:{query:$q,top_k:5}}}')"

out="$(printf '%s\n%s\n%s\n%s\n' "$init" "$note" "$stats_req" "$proj_req" | timeout 10 "$SM_BIN" --memory-dir "$SM_DIR" 2>/dev/null)" || exit 0

text="$(printf '%s' "$out" | PROJ="$proj_name" python3 -c '
import sys, json, os
proj=os.environ.get("PROJ","")
stats=None; proj_hits=[]
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except Exception: continue
    if o.get("id")==2:
        try: stats=json.loads(o["result"]["content"][0]["text"])
        except Exception: pass
    if o.get("id")==3:
        try:
            r=json.loads(o["result"]["content"][0]["text"])
            res=sorted(r.get("results",[]), key=lambda x:x.get("cosine_similarity",0), reverse=True)
            if res and res[0].get("cosine_similarity",0) >= 0.60:
                top=res[0]["cosine_similarity"]
                proj_hits=[x for x in res if x.get("cosine_similarity",0) >= max(0.56, top-0.12)][:3]
        except Exception: pass
if not stats or not stats.get("ok"): sys.exit(0)
facts=stats.get("facts",0); docs=stats.get("documents",0)
chunks=stats.get("chunks",0); edges=stats.get("graph_edges",0)
lines=[]
lines.append(f"Persistent semantic memory is ACTIVE (semantic-memory MCP server): {facts} facts, {docs} docs, {chunks} chunks, {edges} graph edges. This is your primary long-term memory across all projects.")
if proj_hits:
    lines.append(f"\nProject-scoped recall for {proj} (verify against current code before relying on it):")
    for h in proj_hits:
        c=" ".join(str(h.get("content","")).split())
        lines.append("- "+(c[:300]+"…" if len(c)>300 else c))
lines.append("\n- RECALL: relevant entries are auto-injected per prompt; also call sm_search / sm_list_facts / sm_get_fact_neighbors yourself before relying on conversation context.")
lines.append("- PERSIST: store durable verified facts with sm_add_fact (sm_search or sm_list_facts first to avoid duplicates).")
lines.append("- DISCIPLINE: never let stored memory outrank current artifacts/repos; record corrections by append/supersede.")
print("\n".join(lines))
' 2>/dev/null)" || exit 0

[ -z "$text" ] && exit 0
jq -nc --arg c "$text" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
exit 0
