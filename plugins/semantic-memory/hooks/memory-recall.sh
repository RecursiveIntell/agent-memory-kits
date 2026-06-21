#!/usr/bin/env bash
# UserPromptSubmit hook — auto-recall from semantic-memory.
# Embeds the prompt, runs hybrid search, injects the most relevant stored facts
# as additionalContext. FAILS OPEN: any error / no good hit -> exit 0, no output.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_resolve.sh"
sm_resolve || exit 0
sm_debug "UserPromptSubmit recall fired"

# nomic embeddings sit on a high baseline (~0.5 for unrelated text), so use a
# RELATIVE gate, not a flat floor: the best hit must clear MINTOP or nothing is
# injected; then keep only near-peers of the best hit, above ABSFLOOR.
MINTOP="${SM_RECALL_MINTOP:-0.58}"
BAND="${SM_RECALL_BAND:-0.12}"
ABSFLOOR="${SM_RECALL_ABSFLOOR:-0.54}"
TOPK="${SM_RECALL_TOPK:-6}"
MAXHITS="${SM_RECALL_MAXHITS:-4}"
MAXLEN="${SM_RECALL_MAXLEN:-320}"

input="$(cat)"
prompt="$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null)" || exit 0
[ -z "$prompt" ] && exit 0
[ "${#prompt}" -lt 12 ] && exit 0
case "$prompt" in /*) exit 0 ;; esac

init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"recall-hook","version":"1"}}}'
note='{"jsonrpc":"2.0","method":"notifications/initialized"}'
req="$(jq -nc --arg q "$prompt" --argjson k "$TOPK" \
  '{jsonrpc:"2.0",id:2,method:"tools/call",params:{name:"sm_search",arguments:{query:$q,top_k:$k}}}')" || exit 0

out="$(printf '%s\n%s\n%s\n' "$init" "$note" "$req" | timeout 8 "$SM_BIN" --memory-dir "$SM_DIR" 2>/dev/null)" || exit 0

body="$(printf '%s' "$out" | MINTOP="$MINTOP" BAND="$BAND" ABSFLOOR="$ABSFLOOR" MAXHITS="$MAXHITS" MAXLEN="$MAXLEN" python3 -c '
import sys, json, os
mintop=float(os.environ["MINTOP"]); band=float(os.environ["BAND"]); absfloor=float(os.environ["ABSFLOOR"])
maxhits=int(os.environ["MAXHITS"]); maxlen=int(os.environ["MAXLEN"])
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
results=sorted(res.get("results",[]), key=lambda r: r.get("cosine_similarity",0), reverse=True)
if not results: sys.exit(0)
top=results[0].get("cosine_similarity",0)
if top < mintop: sys.exit(0)
keep=[r for r in results if r.get("cosine_similarity",0) >= max(absfloor, top-band)][:maxhits]
out=[]
for r in keep:
    c=" ".join(str(r.get("content","")).split())
    if len(c)>maxlen: c=c[:maxlen-1]+"…"
    out.append("- "+c)
print("\n".join(out))
' 2>/dev/null)" || exit 0

[ -z "$body" ] && exit 0

header="Relevant entries from your persistent semantic memory, auto-retrieved for this prompt. Treat as recall to consider, NOT ground truth — verify against current artifacts/repos before acting, and never let memory outrank current sources:"
full="$header"$'\n'"$body"
jq -nc --arg c "$full" '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
exit 0
