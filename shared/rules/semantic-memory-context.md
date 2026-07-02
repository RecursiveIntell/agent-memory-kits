# semantic-memory context

Use semantic-memory as durable recall before non-trivial work.

When starting a task, retrieve relevant memory first by one of these routes:

1. Prefer the semantic-memory MCP tools if available:
   - call `sm_search` for simple recall;
   - call `sm_search_with_routing` / routed search for synthesis, contradiction, timeline, relationship, or multi-hop questions;
   - use `sm_search_conversations` only for past conversation recall.

2. If MCP tool calling is not available but shell commands are allowed, run:

   ```bash
   /ABSOLUTE/PATH/TO/semantic-memory-agent-kits/shared/scripts/semantic-memory-context.py --prompt "$USER_TASK"
   ```

3. Treat retrieved memory as recall to consider, not ground truth. Current user messages, current files, live command output, and checked sources outrank memory.

4. Save only durable, high-signal facts. Prefer append/supersession over deletion. Do not save task progress, temporary TODOs, commit IDs, PR IDs, or facts likely stale within a week.

5. If a task touches a codebase, prefer namespace `code:<repo-name>` for codebase facts and include source/path evidence where possible.
