# Plugin Update Plan — Post Gap-Fix 2026-06-24

## Context

The semantic-memory-mcp server just had 11 gaps fixed:
- 5 HTTP endpoint fixes (verify-integrity, record-outcome, search-routed, /discord added, RL persistence)
- 15 new MCP tools added (33 -> 48 active tools)
- Library: save_routing_policy/load_routing_policy added

The Claude Code plugin (v0.4.1) and Codex plugin (v0.3.1) are both stale relative to these changes. This plan covers updating the Claude Code kit first (it's the public-facing one), then the Codex plugin.

## What changed that affects the plugin

### Hook-level changes (the plugin's 3 hooks need updates)
1. /search-routed now runs the full pipeline (decoder, discord, factor-graph) — the plugin's recall hook doesn't use /search-routed at all (it only uses /search). It could now benefit from routed search for complex queries.
2. /record-outcome now persists RL feedback — the plugin's recall hook doesn't call /record-outcome. It should, so the RL routing policy learns from Claude Code sessions too.
3. /verify-integrity now does real integrity checks — the plugin's primer hook doesn't call /verify-integrity. It could.
4. /discord endpoint now exists — the plugin's recall hook could use it for second-order retrieval, but this is optional (the MCP tool sm_discord_search is available).

### Tool count change (33 -> 48)
The plugin.json description says "34 sm_* tools". It needs to say 48. The memory-keeper agent description also references the tool surface. However, the 15 new tools are admin/audit tools — they don't need to be in the agent's daily-use vocabulary. The description should mention them as a group, not list them.

### Skills updates
The plugin's 4 skills (memory-capture, memory-curator, memory-sync, knowledge-graph-explorer) are already aligned with the Hermes versions we created. The memory-curator skill should mention sm_reconcile, sm_vacuum, sm_reembed_all as maintenance tools.

## Plan

### Phase 1: Hook updates (the important part)

#### 1a. Upgrade memory-recall.sh to use /search-routed for complex queries

Current: the recall hook does a flat /search for every query. It has no query classification, no routed search, no RL feedback, no rerank chaining.

Target: add a lightweight query classifier (reuse the Hermes sm-recall.py approach — keyword-based A/B/C/D/E classification), use /search for class A, /search-routed for class B/C/D/E, call /record-outcome after every search, and optionally chain /rerank for class C/D.

Approach: The shell hook can do basic keyword classification with case/esac. It doesn't need Python-level sophistication — a few grep patterns for contradiction/synthesis/temporal/multi-hop signals is enough. The key wins are:
- /search-routed for complex queries (now gives full pipeline)
- /record-outcome after every search (now persists RL)

Files: memory-recall.sh, _resolve.sh (add sm_http_post helper)

#### 1b. Upgrade memory-primer.sh to call /verify-integrity

Current: the primer hook calls /stats and does project-scoped /search.

Target: also call GET /verify-integrity and include the result in the primer context. If integrity fails, warn loudly (this is now a real check, not a fake).

Files: memory-primer.sh

#### 1c. Add /discord support to the recall hook (optional)

For class B (multi-hop) queries, after the initial /search, call POST /discord with the direct_ids to get second-order results. This is a bonus — the MCP tool sm_discord_search is already available to the agent. The hook-level benefit is that second-order results are injected as context before the agent even starts reasoning.

Decision: SKIP for now. The recall hook should stay simple. The agent can call sm_discord_search itself when it needs second-order retrieval. Adding /discord to the hook would increase latency for every multi-hop query.

### Phase 2: Metadata updates

#### 2a. Update plugin.json
- Version: 0.4.1 -> 0.5.0 (breaking change: hook behavior changes)
- Description: "34 sm_* tools" -> "48 sm_* tools" (or just say "full sm_* tool surface" to avoid churn)
- Add mention of RL-routed search, real integrity checks

#### 2b. Update memory-keeper.md agent
- Add the 15 new tools to the capabilities list (grouped by category)
- Mention sm_reconcile, sm_vacuum, sm_reembed_all under "Curate"
- Mention sm_get_search_receipt, sm_replay_search_receipt under "Audit"
- Mention sm_query_* under "Bitemporal queries"

#### 2c. Update memory-curator skill
- Add sm_reconcile, sm_vacuum, sm_reembed_all, sm_embeddings_are_dirty to the reconciliation playbook
- Mention sm_get_search_receipt for audit trails

### Phase 3: Skills alignment

#### 3a. Diff the plugin skills against the Hermes skills
The Hermes skills (created earlier this session) were adapted from the plugin skills. The plugin skills should be the canonical source. Check for any divergence and merge back.

#### 3b. Add a memory-maintenance skill
The new maintenance tools (sm_vacuum, sm_reembed_all, sm_embeddings_are_dirty, sm_reconcile) deserve a focused skill. The memory-curator skill already covers auditing, but maintenance is a separate workflow:
1. Check sm_embeddings_are_dirty
2. If dirty, sm_reembed_all
3. sm_vacuum to compact the DB
4. sm_reconcile to fix any integrity issues
5. sm_get_search_receipt to verify search reproducibility

### Phase 4: Codex plugin update (lower priority)

The Codex plugin (v0.3.1) is more stale — it references 30 tools and doesn't have the warm HTTP server. The Codex plugin should be updated to:
1. Use run-server.sh with --http-port (same as Claude Code kit)
2. Update the recall hook to use /search-routed + /record-outcome
3. Update tool count from 30 to 48
4. Align skills with the Claude Code kit

This can be done in a follow-up since Codex is the least-used platform.

### Phase 5: Tool count management

48 tools is above the 15-25 optimal range. Options:
1. **Feature-gate the admin tools**: Put sm_vacuum, sm_reembed_all, sm_reconcile, sm_get_search_receipt, sm_replay_search_receipt, sm_query_*, sm_import_* behind a "maintenance" feature flag. They only appear when the feature is enabled. This keeps the daily-use tool list at ~33.
2. **Group in the description**: Keep all tools but describe them as "33 daily-use + 15 admin/audit" so the agent knows the admin tools exist but doesn't try to use them for normal queries.
3. **Do nothing**: The agent already has 33 tools it was selecting from. Adding 15 more that it rarely sees in practice (they have specific descriptions that won't match normal queries) may not degrade selection significantly.

Recommendation: Option 2 for now (group in description). If selection quality degrades, switch to option 1 (feature-gating).

### Phase 6: Testing

1. Test the upgraded recall hook with a simple query (should use /search)
2. Test with a complex query (should use /search-routed + /record-outcome)
3. Test the primer hook (should call /verify-integrity)
4. Test the full plugin install flow (/plugin install -> /memory-setup -> verify hooks fire)
5. Verify the warm HTTP server starts correctly with the new binary

### Phase 7: Release

1. Commit changes to the semantic-memory-claude-kit repo
2. Tag as v0.5.0
3. Push to GitHub
4. Update the marketplace listing
5. Reinstall the MCP server binary: cargo install semantic-memory-mcp
6. Restart Claude Code to pick up the new hooks

## File change summary

| File | Change | Priority |
|---|---|---|
| hooks/memory-recall.sh | Add query classification, /search-routed, /record-outcome | P0 |
| hooks/memory-primer.sh | Add /verify-integrity call | P1 |
| hooks/_resolve.sh | Add sm_http_post helper for POST requests | P0 |
| .claude-plugin/plugin.json | Version bump, tool count, description | P1 |
| agents/memory-keeper.md | Add 15 new tools to capabilities | P2 |
| skills/memory-curator/SKILL.md | Add maintenance tools to playbook | P2 |
| skills/memory-maintenance/SKILL.md | New skill for maintenance workflow | P3 |
| README.md | Update tool count, HTTP endpoint count, hook descriptions | P2 |

## What NOT to change

- The 3-hook structure (SessionStart, UserPromptSubmit, PreCompact) is correct. Don't add more hooks.
- The fail-open design. All hooks must continue to fail silently.
- The warm HTTP server pattern. It's the right approach.
- The _resolve.sh shared resolver. It's clean.
- The ingest_codebase.py. It's already aligned.