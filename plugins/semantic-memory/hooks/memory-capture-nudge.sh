#!/usr/bin/env bash
# PreCompact hook — nudge to persist durable facts before context is compacted.
# Does NOT write anything itself (model-driven capture, with judgment). FAILS OPEN.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_resolve.sh" 2>/dev/null || true
command -v jq >/dev/null 2>&1 || exit 0
sm_debug "PreCompact capture-nudge fired" 2>/dev/null || true

text="Context is about to be compacted and detail will be lost. Before continuing, persist any DURABLE, VERIFIED facts learned this session into semantic memory with sm_add_fact (pick a namespace; sm_search first to avoid duplicates). Store only things worth remembering across sessions — decisions, stable project/config facts, corrections — not ephemeral conversation. Do not auto-dump; write with judgment, and never let unverified claims become stored truth."

jq -nc --arg c "$text" '{hookSpecificOutput:{hookEventName:"PreCompact",additionalContext:$c}}'
exit 0
