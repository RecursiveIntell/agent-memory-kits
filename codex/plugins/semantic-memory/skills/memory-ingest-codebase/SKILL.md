---
name: memory-ingest-codebase
description: Ingest or refresh a repository into semantic-memory for Codex using the deterministic codebase ingester, including dry runs, namespaces, dedupe, manifests, components, and graph edges. Prefer memory-sync for routine stale repo refreshes.
---

# Memory Ingest Codebase

Use this skill when the user asks to add, ingest, index, refresh, or update a repository in semantic memory. For routine stale-memory refresh after repo changes, `memory-sync` is the canonical workflow.

## Workflow

1. Locate the plugin root. Prefer `/home/sikmindz/plugins/semantic-memory` when present; otherwise search upward or use the installed plugin cache.
2. Run a dry run first:
   `python3 <plugin-root>/scripts/ingest_codebase.py --path <repo> --dry-run`
3. Review the reported namespace, language counts, manifests, component facts, durable facts, and graph edge count.
4. Run the write path with dedupe when ingestion is appropriate:
   `python3 <plugin-root>/scripts/ingest_codebase.py --path <repo> --dedupe`
5. Search or enumerate the resulting namespace with `sm_search`, `sm_list_namespaces`, and `sm_list_facts(namespace="code:<slug>")` before claiming ingestion worked.

## Namespace Rules

- Default namespace is `code:<repo-slug>`.
- Use `--namespace <ns>` only when the user asks for a specific namespace or the repo slug would be ambiguous.
- For monorepos, keep the root namespace stable and rely on component facts and graph edges for routing.

## Safety

Do not ingest secrets, credential-bearing logs, generated artifacts, vendored dependency trees, or volatile command output. If a dry run shows an unexpectedly large or sensitive scope, stop and narrow the repo path or ignore rules before writing.
