---
name: memory-sync
description: Keep a codebase's memory current. Use when the user asks to sync, refresh, re-ingest, or update memory for a repository (e.g. after pulling changes or finishing work), or says "the memory for this project is stale". Re-ingests the repo idempotently (dedupe) so only new/changed components are added.
---

# Memory sync

Refresh the semantic-memory facts + dependency graph for a codebase so they match the current source — without creating duplicates.

## Workflow

1. **Resolve the target.** Default to the current working directory's git root; otherwise use the path the user gives.
2. **Show the delta.** Dry-run first so the user sees what's there vs. new:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_codebase.py" --path <repo> --dry-run`
   (Note: `${CLAUDE_PLUGIN_ROOT}` is the plugin root; the ingester is under its `scripts/`.)
3. **Sync idempotently.** Run with `--dedupe` so unchanged facts are skipped and only new/changed components are written; the graph still links up because existing fact IDs are reused:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_codebase.py" --path <repo> --dedupe`
4. **Report** the namespace (`code:<slug>`), how many facts were newly written vs. reused, and the edge count.

## Notes
- Re-ingest is append/idempotent — it never deletes. A *changed* component writes a new fact (the old one remains); if you need the old one retired, hand off to `/semantic-memory:memory-curator` to supersede it.
- For a quick check of what's already stored for the project, use `sm_list_namespaces` then `sm_list_facts(namespace="code:<slug>")`.
