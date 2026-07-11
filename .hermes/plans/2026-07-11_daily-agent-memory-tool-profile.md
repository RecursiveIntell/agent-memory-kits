# Daily Agent Memory Tool Profile Plan

Goal: expose a bounded 15-tool semantic-memory surface to Claude and Codex while preserving the 3-tool autonomous profile and 60-tool full admin profile.

Contract:
- `agent` exposes exactly: sm_search_witnessed, sm_get_search_receipt, sm_get_fact, sm_add_fact, sm_supersede_fact, sm_update_fact, sm_set_provenance, sm_get_fact_neighbors, sm_add_graph_edge, sm_graph_path, sm_list_namespaces, sm_search_conversations, sm_stats, sm_decide_assertion_authority, sm_decide_action_authority.
- `agent` excludes deletion, import/export, vacuum, re-embedding, reconciliation, lifecycle, parsing, decoder, raw/unwitnessed search, and claim administration.
- `lean` and `standard` remain the 3 governed tools.
- `full` remains all 60 tools and is used only by semantic-memory-admin.

TDD:
1. Add failing integration test for exact `agent` surface and exclusions.
2. Run focused test and capture RED.
3. Implement profile routing and CLI help.
4. Run focused and full MCP suites.
5. Switch Claude/Codex daily launchers and Codex installer/doctor defaults to `agent`; admin launchers remain `full`.
6. Bump plugin patch versions, refresh installed caches/config.
7. Verify installed Claude and Codex daily launchers expose exactly 15 tools and admin exposes 60.
8. Commit locally; do not push.
