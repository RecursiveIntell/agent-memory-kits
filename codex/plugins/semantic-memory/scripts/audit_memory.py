#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERIES = [
    "current Codex semantic-memory plugin version hooks skills MCP tools",
    "semantic-memory-mcp v0.3 direct read tools conversation memory",
    "current semantic-memory setup for Codex and Claude stale superseded",
    "ingest repository into semantic memory with dedupe namespace",
]


def rpc_call(tool: str, arguments: dict | None = None, timeout: int = 30) -> dict | None:
    reqs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "semantic-memory-audit", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments or {}},
        },
    ]
    proc = subprocess.run(
        [str(ROOT / "scripts/run-server.sh")],
        input="\n".join(json.dumps(item) for item in reqs) + "\n",
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") != 2:
            continue
        try:
            return json.loads(msg["result"]["content"][0]["text"])
        except Exception:
            return None
    return None


def namespace_counts(namespaces: list[str]) -> dict[str, int]:
    counts = {}
    for namespace in namespaces:
        total = 0
        limit = 100
        offset = 0
        while True:
            result = rpc_call("sm_list_facts", {"namespace": namespace, "limit": limit, "offset": offset})
            page_count = int((result or {}).get("count", 0))
            total += page_count
            if page_count < limit:
                break
            offset += limit
        counts[namespace] = total
    return counts


def topology_summary(topology: dict | None) -> dict:
    if not topology or not topology.get("ok"):
        return {"ok": False}
    report = str(topology.get("report") or "")
    context_match = re.search(r"MissingContext:\s*(\d+)", report)
    link_match = re.search(r"MissingLink:\s*(\d+)", report)
    missing_context = int(context_match.group(1)) if context_match else 0
    missing_link = int(link_match.group(1)) if link_match else 0
    return {
        "ok": True,
        "betti_0": (topology.get("betti_numbers") or {}).get("betti_0"),
        "betti_1": (topology.get("betti_numbers") or {}).get("betti_1"),
        "edges_loaded": topology.get("edges_loaded_from_store"),
        "missing_context": missing_context,
        "missing_link": missing_link,
    }


def retrieval_cases(queries: list[str], top_k: int, superseded_targets: set[str]) -> list[dict]:
    rows = []
    for query in queries:
        query_l = query.lower()
        allows_superseded = any(term in query_l for term in ("supersed", "stale", "obsolete", "histor", "old fact", "previous fact"))
        plain = rpc_call("sm_search", {"query": query, "top_k": top_k}) or {}
        routed = rpc_call("sm_search_with_routing", {"query": query, "top_k": top_k}) or {}
        plain_results = plain.get("results") or []
        routed_results = routed.get("results") or []
        plain_top = plain_results[0].get("result_id") if plain_results else None
        routed_top = routed_results[0].get("result_id") if routed_results else None
        rows.append(
            {
                "query": query,
                "plain_top": plain_top,
                "plain_score": plain_results[0].get("cosine_similarity") if plain_results else None,
                "routed_top": routed_top,
                "routed_score": routed_results[0].get("score") if routed_results else None,
                "routing": (routed.get("routing_decision") or {}).get("reasoning"),
                "plain_top_superseded": plain_top in superseded_targets,
                "routed_top_superseded": routed_top in superseded_targets,
                "stale_risk": bool(
                    ((plain_top in superseded_targets) and not allows_superseded)
                    or ((routed_top in superseded_targets) and not allows_superseded)
                    or (
                        ("current" in query_l or "stale" in query_l or "supersed" in query_l)
                        and plain_results
                        and routed_results
                        and plain_top != routed_top
                    )
                ),
            }
        )
    return rows


def supersession_summary() -> dict:
    graph = rpc_call("sm_list_graph_edges", {}) or {}
    edges = graph.get("edges") or []
    supersedes = [edge for edge in edges if "supersedes" in json.dumps(edge, sort_keys=True)]
    superseded_targets = sorted({edge.get("target") for edge in supersedes if edge.get("target")})
    return {
        "ok": bool(graph.get("ok")),
        "supersedes_edges": len(supersedes),
        "superseded_targets": superseded_targets,
        "recent_examples": supersedes[-5:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only semantic-memory health and ROI audit.")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--query", action="append", help="extra retrieval query to evaluate")
    args = parser.parse_args()

    stats = rpc_call("sm_stats") or {}
    namespaces = rpc_call("sm_list_namespaces") or {}
    namespace_list = namespaces.get("namespaces") or []
    sessions = rpc_call("sm_list_sessions", {"limit": 20, "offset": 0}) or {}
    community = rpc_call("sm_community", {"resolution": 1.0, "seed": 42}) or {}
    topology = topology_summary(rpc_call("sm_topology"))
    supersession = supersession_summary()
    superseded_targets = set(supersession.get("superseded_targets") or [])
    result = {
        "ok": bool(stats.get("ok") and namespaces.get("ok")),
        "stats": stats,
        "namespace_counts": namespace_counts(namespace_list),
        "sessions": {"count": sessions.get("count", 0), "latest": (sessions.get("sessions") or [])[:3]},
        "graph": {
            "topology": topology,
            "community_count": community.get("community_count"),
            "contradiction_count": community.get("contradiction_count"),
        },
        "supersession": supersession,
        "retrieval_cases": retrieval_cases(DEFAULT_QUERIES + (args.query or []), args.top_k, superseded_targets),
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    print("Semantic Memory Audit")
    print(f"facts={stats.get('facts', 0)} docs={stats.get('documents', 0)} chunks={stats.get('chunks', 0)} edges={stats.get('graph_edges', 0)} messages={stats.get('messages', 0)}")
    print("namespaces=" + ", ".join(f"{name}:{count}" for name, count in result["namespace_counts"].items()))
    print(
        "graph="
        f"components:{topology.get('betti_0')} cycles:{topology.get('betti_1')} "
        f"missing_context:{topology.get('missing_context')} missing_link:{topology.get('missing_link')} "
        f"communities:{community.get('community_count')} contradictions:{community.get('contradiction_count')}"
    )
    supersession = result["supersession"]
    print(f"supersession_edges={supersession.get('supersedes_edges', 0)}")
    print(f"sessions={result['sessions']['count']}")
    print("retrieval:")
    for row in result["retrieval_cases"]:
        marker = "STALE-RISK" if row["stale_risk"] else ("OK" if row["plain_top"] or row["routed_top"] else "MISS")
        print(f"- {marker} {row['query']}")
        print(f"  plain={row['plain_top']} routed={row['routed_top']}")
        if row["plain_top_superseded"] or row["routed_top_superseded"]:
            print("  superseded_top=true")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
