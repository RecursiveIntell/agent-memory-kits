---
name: knowledge-graph-explorer
description: Explore the semantic-memory knowledge graph. Use when the user asks what is related to a topic, how two things or facts are connected, what is known about X across the graph, or wants to see clusters/communities in their memory. Chains hybrid search with second-order (discord) retrieval, shortest-path, and community detection, and can render the result as an interactive HTML graph.
---

# Knowledge graph explorer

Go beyond a flat search: traverse the typed graph to surface related, adjacent, and connecting knowledge that a single query misses.

## Choose the question type

**"What's related to X / what do I know about X?"**
1. `sm_search(X)` → take the top `result_id`s (these are the direct hits).
2. `sm_discord_search(direct_result_ids)` → second-order neighbors: facts connected to your hits through the graph but not themselves direct matches. This is the high-value step.
3. Optionally `sm_community` → which community X sits in, and its members.
4. Synthesize: what's central, what's adjacent, and the relationships between them.

**"How are X and Y connected?"**
1. `sm_search(X)` and `sm_search(Y)` → resolve each to a `result_id`.
2. `sm_graph_path(from_id, to_id)` → the shortest path with per-hop edge evidence (relation, weight). Explain the chain in plain language.

**"Show me the structure / clusters."**
1. `sm_community(resolution)` → communities and members.
2. `sm_topology` → components, cycles, and gaps.
3. Optionally `sm_factor_graph` with initial beliefs → propagated confidence across the graph.

## Optional: render an interactive graph

When a visual would help, gather the subgraph (the nodes from search/discord and the edges from `sm_list_graph_edges` for those nodes), then produce a **self-contained HTML** force/spring graph (inline SVG + vanilla JS, no external assets) and present it with the Artifact tool. Nodes = facts (label with a short snippet), edges = relations (label with the relation type). Keep it CSP-safe: everything inline, no CDN.

## Tips
- Discord search is what makes this worth more than `sm_search` — always run it for "related to" questions.
- Report edge **types/weights** (e.g. `depends_on`, weight 3.0 for hubs) — they carry meaning.
- If the graph is sparse around the topic, say so and suggest running `/semantic-memory:memory-curator` to fill gaps.
