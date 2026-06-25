#!/usr/bin/env bash
# SessionStart hook — prime the session with semantic-memory status, the recall/
# persist protocol, AND project-scoped recall: facts relevant to the current repo
# (from the hook's cwd, git-root aware) injected up front. FAILS OPEN.
#
# Warm-first: query the warm HTTP server (POST /stats + POST /search) so the
# embedder stays loaded. Cold fallback (spawn the binary over stdio) only when
# the warm server is unreachable. Both feed the same parser.
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
# Only do project-scoped recall inside a real git repo that isn't the home dir,
# otherwise a generic cwd (e.g. $HOME) injects loosely-related noise.
do_proj=1
{ [ -z "$proj_root" ] || [ "$proj_root" = "$HOME" ]; } && do_proj=0

# --- gather stats + project hits into two normalized JSON blobs, warm-first ---
stats_json=""
proj_json=""
if sm_warm; then
  sm_debug "primer via warm HTTP ${SM_HTTP}"
  stats_json="$(curl -fsS -m 3 -X POST "${SM_HTTP}/stats" 2>/dev/null)" || stats_json=""
  if [ "$do_proj" = "1" ] && [ -n "$stats_json" ]; then
    reqbody="$(jq -nc --arg q "$proj_name codebase project overview" '{query:$q,top_k:5}')"
    proj_json="$(curl -fsS -m 4 -X POST "${SM_HTTP}/search" \
      -H 'content-type: application/json' -d "$reqbody" 2>/dev/null)" || proj_json=""
  fi
fi
if [ -z "$stats_json" ]; then
  sm_debug "primer via cold stdio"
  init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"primer-hook","version":"1"}}}'
  note='{"jsonrpc":"2.0","method":"notifications/initialized"}'
  stats_req='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"sm_stats","arguments":{}}}'
  if [ "$do_proj" = "1" ]; then
    proj_req="$(jq -nc --arg q "$proj_name codebase project overview" \
      '{jsonrpc:"2.0",id:3,method:"tools/call",params:{name:"sm_search",arguments:{query:$q,top_k:5}}}')"
    out="$(printf '%s\n%s\n%s\n%s\n' "$init" "$note" "$stats_req" "$proj_req" | timeout 10 "$SM_BIN" --memory-dir "$SM_DIR" 2>/dev/null)" || exit 0
  else
    out="$(printf '%s\n%s\n%s\n' "$init" "$note" "$stats_req" | timeout 10 "$SM_BIN" --memory-dir "$SM_DIR" 2>/dev/null)" || exit 0
  fi
  # Unwrap JSON-RPC -> the inner {stats} / {results} blobs the parser expects.
  stats_json="$(printf '%s' "$out" | python3 -c '
import sys, json
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except Exception: continue
    if o.get("id")==2:
        try: sys.stdout.write(o["result"]["content"][0]["text"])
        except Exception: pass
' 2>/dev/null)"
  proj_json="$(printf '%s' "$out" | python3 -c '
import sys, json
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except Exception: continue
    if o.get("id")==3:
        try: sys.stdout.write(o["result"]["content"][0]["text"])
        except Exception: pass
' 2>/dev/null)"
fi
[ -z "$stats_json" ] && exit 0

text="$(STATS="$stats_json" PROJ_JSON="$proj_json" PROJ="$proj_name" python3 -c '
import sys, json, os
proj=os.environ.get("PROJ","")
try: stats=json.loads(os.environ.get("STATS","") or "{}")
except Exception: sys.exit(0)
if not stats or stats.get("ok") is False: sys.exit(0)
proj_hits=[]
pj=os.environ.get("PROJ_JSON","")
if pj:
    try:
        r=json.loads(pj)
        res=r.get("results",[])
        have_cos=any(x.get("cosine_similarity") is not None for x in res)
        if have_cos:
            res=sorted(res, key=lambda x:(x.get("cosine_similarity") or 0), reverse=True)
            if res and (res[0].get("cosine_similarity") or 0) >= 0.60:
                top=res[0]["cosine_similarity"]
                proj_hits=[x for x in res if (x.get("cosine_similarity") or 0) >= max(0.56, top-0.12)][:3]
        else:
            res=sorted(res, key=lambda x:(x.get("score") or 0), reverse=True)
            if res and (res[0].get("score") or 0) > 0:
                top=res[0]["score"]
                proj_hits=[x for x in res if (x.get("score") or 0) >= top*0.5][:3]
    except Exception: pass
facts=stats.get("facts",0); docs=stats.get("documents",0); chunks=stats.get("chunks",0)
edges=stats.get("graph_edges")
head=f"Persistent semantic memory is ACTIVE (semantic-memory MCP server): {facts} facts, {docs} docs, {chunks} chunks"
if edges is not None: head+=f", {edges} graph edges"
head+=". This is your primary long-term memory across all projects."
lines=[head]
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
