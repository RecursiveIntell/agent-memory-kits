#!/usr/bin/env bash
# UserPromptSubmit hook — auto-recall from semantic-memory.
# Embeds the prompt, runs hybrid search, injects the most relevant stored facts
# as additionalContext. FAILS OPEN: any error / no good hit -> exit 0, no output.
#
# Adaptive routing: classifies the query (A/B/C/D/E) and uses:
#   - Class A (simple): flat /search (fast)
#   - Class B/C/D/E (complex): /search-routed (full pipeline: decoder, discord,
#     factor-graph when the server supports it)
# After search, calls /record-outcome for RL routing feedback (now persisted).
#
# Fast path: query the warm HTTP server (embedder already loaded, ~ms). Cold
# fallback: spawn the binary over stdio (reloads the model, ~seconds) only when
# the warm server is unreachable. Both yield a {results:[...]} object that the
# same gate parses.
#
# Dual gating: warm HTTP returns fused RRF scores (0.01-0.03 range); cold stdio
# returns cosine_similarity (0.0-1.0 with nomic's high ~0.5 baseline). The gate
# uses cosine band+floor on cold path, relative RRF threshold on warm path.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_resolve.sh"
sm_resolve || exit 0
sm_debug "UserPromptSubmit recall fired"

# Gating thresholds
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

# Classify query complexity
query_class="$(sm_classify_query "$prompt")"
sm_debug "recall: query class=$query_class prompt=${prompt:0:60}"

# --- fetch a {results:[...]} object, warm-first ---
use_cosine_gate=false
payload=""
if sm_warm; then
  sm_debug "recall via warm HTTP ${SM_HTTP}"
  if [ "$query_class" = "A" ]; then
    # Simple: flat search
    reqbody="$(jq -nc --arg q "$prompt" --argjson k "$TOPK" '{query:$q,top_k:$k}')"
    payload="$(curl -fsS -m 4 -X POST "${SM_HTTP}/search" \
      -H 'content-type: application/json' -d "$reqbody" 2>/dev/null)" || payload=""
  else
    # Complex: routed search (full pipeline on the server)
    reqbody="$(jq -nc --arg q "$prompt" --argjson k "$TOPK" --arg c "$query_class" \
      '{query:$q,top_k:$k,query_class:$c}')"
    payload="$(curl -fsS -m 6 -X POST "${SM_HTTP}/search-routed" \
      -H 'content-type: application/json' -d "$reqbody" 2>/dev/null)" || payload=""
    # If routed search failed, fall back to flat search
    if [ -z "$payload" ]; then
      reqbody="$(jq -nc --arg q "$prompt" --argjson k "$TOPK" '{query:$q,top_k:$k}')"
      payload="$(curl -fsS -m 4 -X POST "${SM_HTTP}/search" \
        -H 'content-type: application/json' -d "$reqbody" 2>/dev/null)" || payload=""
    fi
  fi
fi
if [ -z "$payload" ]; then
  sm_debug "recall via cold stdio"
  use_cosine_gate=true
  init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"recall-hook","version":"1"}}}'
  note='{"jsonrpc":"2.0","method":"notifications/initialized"}'
  req="$(jq -nc --arg q "$prompt" --argjson k "$TOPK" \
    '{jsonrpc:"2.0",id:2,method:"tools/call",params:{name:"sm_search",arguments:{query:$q,top_k:$k}}}')"
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

# Record outcome for RL routing feedback (now persisted server-side)
if sm_warm; then
  outcome="good"
  # Quick score check to decide good vs bad
  top_check="$(printf '%s' "$payload" | python3 -c '
import sys, json
try:
  r=json.load(sys.stdin)
  res=r.get("results",[])
  if res:
    s=res[0].get("score") or res[0].get("cosine_similarity") or 0
    print(s)
  else:
    print(0)
except: print(0)
' 2>/dev/null)" || top_check="0"
  # For RRF scores (warm), >0.01 is decent. For cosine (cold), >0.58 is decent.
  if [ "$use_cosine_gate" = "true" ]; then
    { [ "$(printf '%.4f' "$top_check" 2>/dev/null || echo 0)" = "0.0000" ] || \
      awk "BEGIN{exit !($top_check < 0.58)}" 2>/dev/null; } && outcome="bad"
  else
    { [ "$(printf '%.4f' "$top_check" 2>/dev/null || echo 0)" = "0.0000" ] || \
      awk "BEGIN{exit !($top_check < 0.01)}" 2>/dev/null; } && outcome="bad"
  fi
  sm_record_outcome "$prompt" "$outcome" "$query_class"
fi

body="$(printf '%s' "$payload" | MINTOP="$MINTOP" BAND="$BAND" ABSFLOOR="$ABSFLOOR" SCOREREL="$SCOREREL" MAXHITS="$MAXHITS" MAXLEN="$MAXLEN" USE_COSINE="$use_cosine_gate" python3 -c '
import sys, json, os
mintop=float(os.environ["MINTOP"]); band=float(os.environ["BAND"]); absfloor=float(os.environ["ABSFLOOR"])
scorerel=float(os.environ["SCOREREL"]); maxhits=int(os.environ["MAXHITS"]); maxlen=int(os.environ["MAXLEN"])
use_cosine=os.environ.get("USE_COSINE","false")=="true"
try: res=json.load(sys.stdin)
except Exception: sys.exit(0)
if not isinstance(res, dict) or res.get("ok") is False: sys.exit(0)
results=res.get("results",[])
if not results: sys.exit(0)
# Dual gating: cosine on cold path, RRF score on warm path
if use_cosine:
    # Cosine gate (cold stdio path)
    have_cos=any(r.get("cosine_similarity") is not None for r in results)
    if have_cos:
        results=sorted(results, key=lambda r: (r.get("cosine_similarity") or 0), reverse=True)
        top=results[0].get("cosine_similarity") or 0
        if top < mintop: sys.exit(0)
        floor=max(absfloor, top-band)
        keep=[r for r in results if (r.get("cosine_similarity") or 0) >= floor][:maxhits]
    else:
        # No cosine in cold path — fall back to RRF
        results=sorted(results, key=lambda r: (r.get("score") or 0), reverse=True)
        top=results[0].get("score") or 0
        if top <= 0: sys.exit(0)
        keep=[r for r in results if (r.get("score") or 0) >= top*scorerel][:maxhits]
else:
    # RRF score gate (warm HTTP path)
    have_cos=any(r.get("cosine_similarity") is not None for r in results)
    if have_cos:
        # Warm path may still include cosine — prefer it when available
        results=sorted(results, key=lambda r: (r.get("cosine_similarity") or 0), reverse=True)
        top=results[0].get("cosine_similarity") or 0
        if top < mintop: sys.exit(0)
        floor=max(absfloor, top-band)
        keep=[r for r in results if (r.get("cosine_similarity") or 0) >= floor][:maxhits]
    else:
        # Pure RRF score (no cosine)
        results=sorted(results, key=lambda r: (r.get("score") or 0), reverse=True)
        top=results[0].get("score") or 0
        if top <= 0: sys.exit(0)
        keep=[r for r in results if (r.get("score") or 0) >= top*scorerel][:maxhits]
out=[]
for r in keep:
    c=" ".join(str(r.get("content","")).split())
    if len(c)>maxlen: c=c[:maxlen-1]+"..."
    out.append("- "+c)
print("\n".join(out))
' 2>/dev/null)" || exit 0

[ -z "$body" ] && exit 0

route_tag=""
[ "$query_class" != "A" ] && route_tag=" (routed: class $query_class)"
header="Relevant entries from your persistent semantic memory, auto-retrieved for this prompt${route_tag}. Treat as recall to consider, NOT ground truth — verify against current artifacts/repos before acting, and never let memory outrank current sources:"
full="$header"$'\n'"$body"
jq -nc --arg c "$full" '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:$c}}'
exit 0