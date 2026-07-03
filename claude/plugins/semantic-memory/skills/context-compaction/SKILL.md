---
name: context-compaction
description: "Use context-governor for receipt-backed context compaction before risky handoffs or compaction events. Preserve high-risk context, store exact fallback receipts, and expand when omitted text matters."
---

# Context Compaction

Use context-governor when a session is long, a handoff is needed, or context is about to be compacted.

## When to use

- Before context compaction (automatic via PreCompact hook where supported)
- When a session is long and you need a concise handoff
- Before passing context to a subagent with a smaller context window
- When you need to recover exact text that was summarized away

## Tools

- `cg_list_receipts` — list stored compaction receipt IDs
- `cg_search` — search receipts and exact fallback content by query
- `cg_expand` — expand exact fallback text for a specific receipt item
- `cg_diff_receipt` — inspect kept/summarized/omitted/quarantined counts and warnings for a receipt

## Rules

1. Prefer exact current conversation context while available. Compacted summaries are background only.
2. Before risky summarization/handoff, preserve active task, acceptance gates, file paths, failing errors, decisions, commands run, and verification receipts.
3. After compaction, if high-risk omitted context matters, use `cg_search` to find it and `cg_expand` to recover exact text.
4. Never treat a compaction receipt as proof that work succeeded. Receipts prove what context was preserved and how to recover exact text.
5. Use `cg_diff_receipt` to check for warnings or high-risk omissions after compaction.

## Shell command (for hosts without hooks)

```bash
shared/scripts/context-governor-compact.py --input transcript.json
```
