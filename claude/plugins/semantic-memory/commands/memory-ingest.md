---
description: "Ingest a codebase into semantic memory (facts + dependency graph). Usage: /memory-ingest <path-to-repo>"
argument-hint: "<path-to-repo> [--dry-run]"
---

Ingest the codebase at `$ARGUMENTS` into the persistent semantic memory store using the bundled language-agnostic ingester.

Steps:
1. Run a dry run first so the user sees the plan:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_codebase.py" --path $ARGUMENTS --dry-run`
2. Briefly summarize what it will write (languages, ecosystems, component count, fact/edge counts).
3. Unless the user passed `--dry-run`, run the real ingestion:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_codebase.py" --path $ARGUMENTS`
4. Report the namespace it wrote to and the final fact/edge counts, and confirm recall works with one `sm_search` over that namespace.

The ingester is deterministic and Grade-A (facts come straight from manifests and source structure). It never deletes existing memory; re-running appends. If the path has no recognised manifests, it still captures repo overview, language stats, layout, and README.
