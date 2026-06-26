---
name: memory-capture
description: Persist durable facts to semantic memory. Use when the user says "remember this", "save that", "note that", "add to memory", "store this", or shares a lasting decision, preference, config detail, or correction worth keeping across sessions. Searches first to avoid duplicates, picks a namespace, writes with sm_add_fact, and links the new fact into the knowledge graph when relevant.
---

# Memory capture

Persist **durable, verified** knowledge into semantic memory — cleanly, without duplicates, with good structure. This is the disciplined *write* path that complements automatic recall.

## What qualifies

Store only things worth remembering across sessions:
- Decisions and their rationale, naming/convention choices
- Stable project/config/environment facts
- User preferences and working agreements
- Corrections that supersede something previously believed

**Do NOT store:** ephemeral conversation, unverified claims, secrets, or anything already obvious from the repo/artifacts. Never let stored memory outrank current artifacts (Doctrine Source Hierarchy).

## Workflow

For each candidate fact:

1. **Dedupe first.** `sm_search` the fact's gist (pass `namespaces` if you know it). For a precise check in a known namespace, `sm_list_facts(namespace)` to scan everything there; read any close match in full with `sm_get_fact(id)`.
   - If a near-identical fact exists → **don't duplicate.** If the new info supersedes it, use `sm_supersede_fact(old_fact_id, content, namespace, reason)` — one call writes the correction, links it, and marks the old one superseded so search filters it automatically. (Don't hand-roll "write new + invalidate edges" anymore.)
   - If it *contradicts* an existing fact → surface the conflict to the user before writing.
2. **Pick a namespace.** Reuse an existing one (`general`, `doctrine`, `projects`, `infrastructure`, `research`, `code:<repo>`, …) or create a clear new one. Keep related facts together.
3. **Write** with `sm_add_fact` — one self-contained fact per call, with a `source` attribution and a date if time-relevant.
4. **Link (optional).** If the fact relates to existing facts, connect them with `sm_add_graph_edge` (entity relation like `belongs_to`, `relates_to`, `supersedes`). Use `result_id`s from step 1 as endpoints.
5. **Confirm.** Report what was stored (namespace + id), and note anything skipped as a duplicate.

## Principles
- Write with judgment — quality over volume. A noisy store is worse than a small one.
- Prefer append/supersede over rewriting; the store is append-only by design.
- One fact = one idea, phrased so it's retrievable months later without this conversation.
