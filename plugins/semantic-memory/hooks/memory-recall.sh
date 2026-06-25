#!/usr/bin/env bash
# UserPromptSubmit hook — auto-recall from semantic-memory.
# Embeds the prompt, runs hybrid search, injects the most relevant stored facts
# as additionalContext. FAILS OPEN: any error / no good hit -> exit 0, no output.
#
# Fast path: query the warm HTTP server (embedder already loaded, ~ms). Cold
# fallback: spawn the binary over stdio (reloads the model, ~seconds) only when
# the warm server is unreachable. Both yield a {results:[...]} object that the
# same gate parses.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_resolve.sh"
sm_resolve || exit 0
sm_debug "UserPromptSubmit recall fired"

# nomic embeddings sit on a high baseline (~0.5 for unrelated text), so use a
# RELATIVE gate, not a flat floor: the best hit must clear MINTOP or nothing is
# injected; then keep only near-peers of the best hit, above ABSFLOOR. The warm
# HTTP /search returns a fused RRF score (no cosine); on that path we gate
# relatively on the score instead (keep hits >= SCOREREL fraction of the top).
# The cold stdio path returns cosine and uses the absolute gates.
MINTOP="${SM_RECALL_MINTOP:-0.58}"
BAND="${SM_RECALL_BAND:-0.12}"
ABSFLOOR="${SM_RECALL_ABSFLOOR:-0.54}"
SCOREREL="${SM_RECALL_SCOREREL:-0.5}"
TOPK="${SM_RECALL_TOPK:-6}"
MAXHITS="${SM_RECALL_MAXHITS:-4}"
MAXLEN="${SM_RECALL_MAXLEN:-320}"

input="$(cat)"
prompt="$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null)" || exit 0
[ -z "$prompt" ] && exit 0
[ "${#prompt}" -lt 12 ] && exit 0
case "$prompt" in /*) exit 0 ;; esac

# --- fetch a {results:[...]} object, warm-first ---
payload=""
if sm_warm; then
  sm_debug "recall via warm HTTP ${SM_HTTP}"
  reqbody="$(jq -nc --arg q "$prompt" --argjson k "$TOPK" '{query:$q,top_k:$k}')" || exit 0
  payload="$(curl -fsS -m 4 -X POST "${SM_HTTP}/search" \
    -H 'content-type: application/json' -d "$reqbody" 2>/dev/null)" || payload=""
fi
if [ -z "$payload" ]; then
  sm_debug "recall via cold stdio"
  init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"recall-hook","version":"1"}}}'
  note='{"jsonrpc":"2.0","method":"notifications/initialized"}'
  req="$(jq -nc --arg q "$prompt" --argjson k "$TOPK" \
    '{jsonrpc:"2.0",id:2,method:"tools/call",params:{name:"sm_search",arguments:{query:$q,top_k:$k}}}')" || exit 0
  out="$(printf '%s\n%s\n%s\n' "$init" "$note" "$req" | timeout 8 "$SM_BIN" --memory-dir "$SM_DIR" 2>/dev/null)" || exit 0
  # Unwrap the JSON-RPC envelope to the inner {results:[...]} so both paths feed
  # the same parser.
  payload="$(printf '%s' "$out" | python3 -c '
import sys, json
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except Exception: continue
    if o.get("id")==2:
        try: sys.stdout.write(o["result"]["content"][0]["text"])
        except Exception: pass
' 2>/dev/null)" || exit 0
fi
[ -z "$payload" ] && exit 0

body="$(printf '%s' "$payload" | MINTOP="$MINTOP" BAND="$BAND" ABSFLOOR="$ABSFLOOR" SCOREREL="$SCOREREL" MAXHITS="$MAXHITS" MAXLEN="$MAXLEN" python3 -c '
import sys, json, os
mintop=float(os.environ["MINTOP"]); band=float(os.environ["BAND"]); absfloor=float(os.environ["ABSFLOOR"])
scorerel=float(os.environ["SCOREREL"]); maxhits=int(os.environ["MAXHITS"]); maxlen=int(os.environ["MAXLEN"])
try: res=json.load(sys.stdin)
except Exception: sys.exit(0)
if not isinstance(res, dict) or res.get("ok") is False: sys.exit(0)
results=res.get("results",[])
if not results: sys.exit(0)
# Prefer cosine_similarity (tuned gates). If absent/null on every hit, gate
# relatively on the fused score instead.
have_cos=any(r.get("cosine_similarity") is not None for r in results)
if have_cos:
    results=sorted(results, key=lambda r: (r.get("cosine_similarity") or 0), reverse=True)
    top=results[0].get("cosine_similarity") or 0
    if top < mintop: sys.exit(0)
    floor=max(absfloor, top-band)
    keep=[r for r in results if (r.get("cosine_similarity") or 0) >= floor][:maxhits]
else:
    results=sorted(results, key=lambda r: (r.get("score") or 0), reverse=True)
    top=results[0].get("score") or 0
    if top <= 0: sys.exit(0)
    keep=[r for r in results if (r.get("score") or 0) >= top*scorerel][:maxhits]
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
