---
name: knowledge-graph-explorer
description: Explore the semantic-memory knowledge graph. Use when the user asks what is related to a topic, how two things or facts connect, what is known across the graph, or wants clusters, communities, graph paths, second-order retrieval, or an interactive graph view.
---

# Knowledge Graph Explorer

Use graph traversal when flat search is not enough.

## Question Types

For "what is related to X" or "what do I know about X":

1. `sm_search(X)` to resolve direct hits.
2. `sm_get_fact_neighbors(result_id)` for each anchor. This returns the fact plus neighbors with content, relation, direction, and weight.
3. `sm_discord_search(direct_result_ids)` for second-order related items. Hydrate ids with `sm_get_fact`.
4. Optionally run `sm_community` for clusters and members.

For "how are X and Y connected":

1. `sm_search(X)` and `sm_search(Y)` to resolve ids.
2. `sm_graph_path(from_id, to_id)` for shortest path and edge evidence.
3. Use `sm_get_fact` for any path ids before explaining the chain.

For "show structure or clusters":

1. `sm_community` for communities.
2. `sm_topology` for components, cycles, and gaps.
3. `sm_factor_graph` when confidence propagation matters.

## Optional Graph View

When a visual helps, generate a self-contained HTML force graph from `sm_get_fact_neighbors` output. Use inline SVG and vanilla JavaScript only. Nodes are fact snippets, edges are relation labels, and edge thickness reflects weight.

## Reporting

Always state whether the graph is sparse, dense, contradictory, or missing links. Memory remains recall; verify current artifacts before acting on graph conclusions.
