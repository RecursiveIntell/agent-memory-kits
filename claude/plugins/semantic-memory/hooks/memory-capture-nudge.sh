#!/usr/bin/env bash
# PreCompact and Stop capture nudge. Does NOT write. FAILS OPEN.
# Claude Code continues the turn when Stop returns additionalContext, so only
# issue that nudge on the first Stop callback. Grok ignores stdout for passive
# lifecycle events, so the Claude-compatible response is inert there.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_resolve.sh" 2>/dev/null || true
command -v jq >/dev/null 2>&1 || exit 0

input="$(cat 2>/dev/null || true)"
event="$(printf '%s' "$input" | jq -r '.hookEventName // .hook_event_name // empty' 2>/dev/null)" || event=""
event_norm="$(printf '%s' "$event" | tr '[:upper:]' '[:lower:]' | tr -d '_')"

hook_event=""
text=""
case "$event_norm" in
  precompact)
    hook_event="PreCompact"
    text="Context is about to be compacted and detail will be lost. Before continuing, persist any DURABLE, VERIFIED facts learned this session into semantic memory with the governed capture path: use sm_search_witnessed first to avoid duplicates and verify authority, then use sm_add_fact only for an admitted durable fact. Store only things worth remembering across sessions — decisions, stable project/config facts, corrections — not ephemeral conversation. Do not auto-dump; write with judgment, and never let unverified claims become stored truth."
    ;;
  stop)
    if printf '%s' "$input" | jq -e '.stop_hook_active == true' >/dev/null 2>&1; then
      sm_debug "capture-nudge skipped on repeated Stop callback" 2>/dev/null || true
      exit 0
    fi
    hook_event="Stop"
    text="Before ending this turn, persist any DURABLE, VERIFIED facts learned this session into semantic memory with the governed capture path: use sm_search_witnessed first to avoid duplicates and verify authority, then use sm_add_fact only for an admitted durable fact. Store only things worth remembering across sessions — decisions, stable project/config facts, corrections — not ephemeral conversation. Do not auto-dump; write with judgment, and never let unverified claims become stored truth."
    ;;
  *)
    sm_debug "capture-nudge skipped on unmatched event '$event'" 2>/dev/null || true
    exit 0
    ;;
esac

sm_debug "$hook_event capture-nudge fired" 2>/dev/null || true
jq -nc --arg c "$text" --arg e "$hook_event" '{hookSpecificOutput:{hookEventName:$e,additionalContext:$c}}'
exit 0
