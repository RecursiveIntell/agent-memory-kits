---
name: memory-maintenance
description: "Run semantic-memory store maintenance. Use when the user asks to compact, vacuum, rebuild indexes, re-embed, check integrity, or fix DB health. Covers the full maintenance workflow: integrity check, re-embed stale vectors, vacuum compact, reconcile FTS indexes, and verify search reproducibility via receipts."
related_skills:
  - semantic-memory-local-operations
  - semantic-memory-retrieval-strategy
  - memory-curator
---

# Memory maintenance

Keep the semantic-memory store healthy at the storage layer. This is the *maintenance* counterpart to `memory-curator` (which handles content-level cleanup like duplicates and contradictions).

## When to use

- "check memory health" / "is the DB ok"
- "compact" / "vacuum" / "rebuild indexes"
- "re-embed" / "embeddings are dirty"
- After changing the embedding model
- After large bulk ingestions
- When search quality degrades suddenly

## Workflow

1. **Check integrity.** Call `sm_stats` for current size. If available, use the HTTP `/verify-integrity` endpoint (warm server) or the MCP tool path:
   - If integrity fails, note the specific issues (WAL checkpoint, FTS index, HNSW).
   - Use `sm_reconcile` with action `"ReportOnly"` to get a detailed report without making changes.
   - If issues are found and the user approves, `sm_reconcile` with action `"RebuildFts"` to rebuild FTS indexes from source data.

2. **Check embedding health.** Call `sm_embeddings_are_dirty` to see if any facts lack embeddings or have stale vectors (wrong dimension, missing).
   - If dirty: `sm_reembed_all` to re-embed every fact with the current model. This is expensive (~138ms per fact on CPU with Candle) so warn the user first.
   - After re-embedding: `sm_vacuum` to compact the DB and reclaim space from old vector data.

3. **Compact the store.** `sm_vacuum` runs SQLite VACUUM to reclaim space and defragment. Safe to run anytime, but especially after large deletions or re-embedding.

4. **Verify search reproducibility** (optional). If search quality seems off:
   - `sm_get_search_receipt(receipt_id)` to retrieve a past search receipt.
   - `sm_replay_search_receipt(receipt_id)` to replay the exact search and compare results.
   - If results differ, the index may be corrupt -- go back to step 1.

5. **Report.** Summarize: what was found, what was fixed, current store health, and any residual issues.

## Tool reference

**HTTP endpoints (always available, not gated by tool profile):**
| Endpoint | Purpose | Cost |
|---|---|---|
| POST /maintenance/check | Combined integrity + embedding health | ~50ms |
| POST /maintenance/vacuum | SQLite VACUUM — compact + defragment | ~1-10s |
| POST /maintenance/reconcile | Fix integrity issues (ReportOnly / RebuildFts / ReEmbed) | varies |
| POST /maintenance/reembed | Re-embed every fact with current model | ~138ms/fact |
| POST /maintenance/compact-hnsw | Compact HNSW index (no-op if usearch) | ~1-5s |
| GET /verify-integrity | Standalone integrity check | ~50ms |

**MCP tools (may be hidden in lean profile -- use HTTP endpoints instead):**
| Tool | Purpose | Cost |
|---|---|---|
| `sm_embeddings_are_dirty` | Check if any facts lack embeddings | ~10ms |
| `sm_reembed_all` | Re-embed every fact with current model | ~138ms/fact (Candle CPU) |
| `sm_vacuum` | SQLite VACUUM — compact + defragment | ~1-10s depending on DB size |
| `sm_reconcile` | Fix integrity issues (ReportOnly / RebuildFts / ReEmbed) | varies |
| `sm_get_search_receipt` | Retrieve a stored search receipt | ~5ms |
| `sm_replay_search_receipt` | Replay a past search to verify reproducibility | ~search cost |

**Auto-management:**
- The primer hook runs /maintenance/check on every session start. If integrity fails, it auto-reconciles with RebuildFts.
- A daily cron job (4am) runs /maintenance/check + /maintenance/vacuum + /maintenance/compact-hnsw. Silent on success, reports only on problems.
- Re-embed is never auto-run (too expensive). The hook warns if embeddings are dirty.

## Tool profile note

These maintenance tools (sm_reconcile, sm_vacuum, sm_reembed_all, sm_embeddings_are_dirty, sm_get_search_receipt, sm_replay_search_receipt) are hidden in the default "lean" tool profile. If they don't appear in the tool list, switch to standard or full by setting `SEMANTIC_MEMORY_TOOL_PROFILE=standard` (or `full`) and restarting the MCP server. No recompilation needed -- it's a runtime gate via rmcp's ToolRouter::disable_route().

## Guardrails

- Always check first, fix second. Never run `sm_reembed_all` or `sm_reconcile` without first confirming there's a problem.
- `sm_reembed_all` is expensive -- warn the user and get approval first.
- `sm_reconcile` with `RebuildFts` is safe but slow on large stores.
- `sm_vacuum` is safe and idempotent.
- Never run maintenance while a bulk ingestion is in progress.