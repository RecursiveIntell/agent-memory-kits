#!/usr/bin/env python3
"""memory-gaps.py — detect knowledge gaps in semantic memory.

Calls the warm semantic-memory HTTP server and analyzes results for:
- Structural gaps: missing namespaces, thin coverage
- Content gaps: shallow facts, missing graph edges, low result counts
- Domain gaps: areas with high query frequency but low recall quality

Falls back to pure-Python analysis if the AiDENs gap_detector binary is absent.

Usage:
  python memory-gaps.py --domain general --out /tmp/gaps.json
  python memory-gaps.py --namespace hermes --top-k 20
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error


def http_base() -> str:
    port = os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", "1739")
    return os.environ.get("SEMANTIC_MEMORY_HTTP_URL", f"http://127.0.0.1:{port}")


def http_get(path: str, timeout: float = 5.0) -> dict | None:
    try:
        with request.urlopen(f"{http_base().rstrip('/')}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def http_post(path: str, payload: dict, timeout: float = 10.0) -> dict | None:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{http_base().rstrip('/')}{path}",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def detect_gaps(domain: str | None, namespace: str | None, top_k: int) -> dict:
    """Detect knowledge gaps by analyzing search results and namespace coverage."""
    gaps = []
    server_available = False

    # Check server health
    health = http_get("/health", timeout=3.0)
    if health and health.get("ok"):
        server_available = True
    else:
        return {
            "schema": "GapReportV1",
            "trace_id": f"trace:memory-gaps:{uuid.uuid4().hex[:16]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_available": False,
            "gaps": [],
            "summary": {"total_gaps": 0, "error": "semantic-memory server unavailable"},
        }

    # Get stats
    stats = http_get("/stats", timeout=5.0) or {}
    fact_count = stats.get("fact_count", 0)
    edge_count = stats.get("edge_count", 0)
    namespaces = stats.get("namespaces", [])

    # Structural gaps: namespaces with very few facts
    ns_gaps = []
    for ns_info in namespaces if isinstance(namespaces, list) else []:
        ns_name = ns_info.get("namespace", "") if isinstance(ns_info, dict) else str(ns_info)
        ns_count = ns_info.get("count", 0) if isinstance(ns_info, dict) else 0
        if ns_count < 5 and ns_name and not ns_name.startswith("_"):
            ns_gaps.append({
                "type": "thin_namespace",
                "namespace": ns_name,
                "fact_count": ns_count,
                "severity": "high" if ns_count == 0 else "medium",
            })

    if ns_gaps:
        gaps.extend(ns_gaps[:20])

    # Content gaps: search for domain/namespace and analyze result quality
    search_queries = []
    if domain:
        search_queries.append(("domain", domain, {"query": domain, "top_k": top_k}))
    if namespace:
        search_queries.append(("namespace", namespace, {"query": namespace, "top_k": top_k, "namespaces": [namespace]}))
    # Always add a broad query
    search_queries.append(("broad", "general knowledge overview", {"query": "overview architecture summary", "top_k": top_k}))

    for label, query_text, payload in search_queries:
        result = http_post("/search", payload, timeout=10.0)
        if not result or not result.get("ok"):
            gaps.append({
                "type": "search_failed",
                "label": label,
                "query": query_text,
                "severity": "high",
            })
            continue

        hits = result.get("results", [])
        if len(hits) < 3:
            gaps.append({
                "type": "low_recall",
                "label": label,
                "query": query_text,
                "result_count": len(hits),
                "severity": "medium" if len(hits) > 0 else "high",
            })

        # Check for shallow content (very short facts)
        shallow = 0
        for hit in hits[:top_k]:
            content = str(hit.get("content") or "")
            if len(content) < 50:
                shallow += 1
        if shallow > len(hits) * 0.5 and len(hits) > 0:
            gaps.append({
                "type": "shallow_content",
                "label": label,
                "query": query_text,
                "shallow_count": shallow,
                "total_count": len(hits),
                "severity": "medium",
            })

        # Check for missing graph edges (facts with no connections)
        no_edges = 0
        for hit in hits[:top_k]:
            rid = hit.get("result_id") or hit.get("id")
            if rid:
                edges = http_get(f"/list-graph-edges?node_id={rid}", timeout=3.0)
                if not edges or len(edges.get("edges", [])) == 0:
                    no_edges += 1
        if no_edges > len(hits) * 0.7 and len(hits) > 2:
            gaps.append({
                "type": "missing_graph_edges",
                "label": label,
                "query": query_text,
                "disconnected_count": no_edges,
                "total_count": len(hits),
                "severity": "low",
            })

    # Edge/fact ratio gap (low connectivity)
    if fact_count > 0 and edge_count > 0:
        ratio = edge_count / fact_count
        if ratio < 0.5:
            gaps.append({
                "type": "low_connectivity",
                "fact_count": fact_count,
                "edge_count": edge_count,
                "ratio": round(ratio, 3),
                "severity": "medium",
            })

    # Deduplicate gaps
    seen = set()
    unique_gaps = []
    for g in gaps:
        key = json.dumps(g, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique_gaps.append(g)

    return {
        "schema": "GapReportV1",
        "trace_id": f"trace:memory-gaps:{uuid.uuid4().hex[:16]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server_available": server_available,
        "stats": {"fact_count": fact_count, "edge_count": edge_count, "namespace_count": len(namespaces) if isinstance(namespaces, list) else 0},
        "gaps": unique_gaps,
        "summary": {
            "total_gaps": len(unique_gaps),
            "high_severity": sum(1 for g in unique_gaps if g.get("severity") == "high"),
            "medium_severity": sum(1 for g in unique_gaps if g.get("severity") == "medium"),
            "low_severity": sum(1 for g in unique_gaps if g.get("severity") == "low"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect knowledge gaps in semantic memory")
    parser.add_argument("--domain", help="Domain to check for gaps")
    parser.add_argument("--namespace", help="Specific namespace to check")
    parser.add_argument("--top-k", type=int, default=15, help="Results to analyze per query")
    parser.add_argument("--out", help="Output file path (default: stdout)")
    args = parser.parse_args()

    report = detect_gaps(args.domain, args.namespace, args.top_k)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Gap report written to {args.out}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()