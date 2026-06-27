---
name: memory-conversation-log
description: Use semantic-memory conversation tools. Trigger when the user asks to recall past sessions, search prior conversations, list memory sessions, save a notable exchange, or log conversation messages into semantic-memory.
---

# Memory Conversation Log

Use the conversation-memory tools for session/message history. These are separate from durable facts.

## Recall

- `sm_search_conversations(query, top_k)`: semantic search over stored messages.
- `sm_list_sessions(limit, offset)`: browse recent sessions.
- `sm_get_messages(session_id, max_tokens)`: read recent messages from one session.

Hydrate and verify important claims against current artifacts before acting.

## Write

Use writes sparingly and only for useful conversation history:

1. `sm_create_session(channel, metadata)` for a container.
2. `sm_add_message(session_id, role, content)` for user, assistant, system, or tool messages.

Prefer `sm_add_fact` for stable project facts, decisions, preferences, and corrections. Conversation logs are for reconstructing context, not authoritative memory.

## Guardrails

Do not log secrets, credentials, private keys, or raw sensitive transcripts. Keep durable facts atomic and source-aware instead of dumping whole conversations.
