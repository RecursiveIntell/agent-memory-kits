---
name: memory-capture
description: Persist durable facts to semantic memory. Use when the user says remember this, save that, note that, add to memory, store this, or shares a lasting decision, preference, config detail, correction, or verified project fact worth keeping across Codex sessions.
---

# Memory Capture

Persist durable, verified knowledge into semantic memory without duplicates.

## What Qualifies

Store only things worth remembering across sessions:

- Decisions and rationale.
- Stable project, config, environment, or workflow facts.
- User preferences and working agreements.
- Corrections that supersede something previously believed.

Do not store ephemeral conversation, unverified claims, secrets, credential-bearing logs, or anything already obvious from current artifacts. Current artifacts outrank memory.

## Workflow

For each candidate fact:

1. Dedupe first.
   - Use `sm_search` for the fact's gist.
   - If the namespace is known, use `sm_list_facts(namespace)` and inspect close matches with `sm_get_fact`.
2. Pick a namespace.
   - Reuse clear namespaces like `codex`, `infrastructure`, `projects`, `user-preferences`, `decisions`, `handoffs`, or `code:<repo>`.
3. Write one fact.
   - Use `sm_add_fact` with concise self-contained content, namespace, source, and date when time matters.
   - If the new fact replaces a verified stale fact, use `sm_supersede_fact` instead so the replacement and `supersedes` edge are created together.
4. Link when useful.
   - Use `sm_add_graph_edge` for durable relationships such as `relates_to`, `belongs_to`, `duplicate_of`, or `reconciles`.
   - Use `sm_add_graph_edge` with relation `supersedes` only as a fallback when linking an already-written replacement fact.
5. Confirm.
   - Report namespace, fact id, and any duplicate skipped.

## Guardrails

If a new fact contradicts an existing one, verify against current artifacts and surface the conflict before writing. Prefer append/supersede over rewriting history.
