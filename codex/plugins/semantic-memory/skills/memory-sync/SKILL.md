---
name: memory-sync
description: Keep a codebase's semantic memory current. Use when the user asks to sync, refresh, re-ingest, or update memory for a repository after pulling changes, finishing work, or finding stale project memory.
---

# Memory Sync

Refresh repository facts and dependency graph edges without creating duplicates.

## Workflow

1. Resolve the target repo. Default to the current git root unless the user gives a path.
2. Dry-run:
   `python3 <plugin-root>/scripts/ingest_codebase.py --path <repo> --dry-run`
3. Review the namespace, languages, ecosystems, component count, facts to write, and graph edges.
4. Sync idempotently:
   `python3 <plugin-root>/scripts/ingest_codebase.py --path <repo> --dedupe`
5. Verify with `sm_list_namespaces`, `sm_list_facts(namespace="code:<slug>")`, or focused `sm_search`.

## Notes

Re-ingestion is append/idempotent. Changed components write new facts; old facts remain for audit. Use `memory-curator` when old facts need superseding or graph edges need invalidation.
