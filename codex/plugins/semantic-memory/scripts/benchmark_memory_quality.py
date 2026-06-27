#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import subprocess
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = os.environ.get("SEMANTIC_MEMORY_HTTP_URL", "http://127.0.0.1:1739")
OUTDIR = Path.home() / ".local/share/semantic-memory/benchmarks"


SEARCH_CASES = [
    {
        "name": "codex plugin current state",
        "endpoint": "/search",
        "payload": {
            "query": "Codex semantic-memory plugin warm HTTP adaptive routing current state",
            "top_k": 8,
            "namespaces": ["codex", "infrastructure"],
        },
        "must_include_any": ["0.7.0+codex", "warm HTTP", "adaptive query"],
        "preferred_namespaces": ["codex"],
    },
    {
        "name": "auto ingest hook",
        "endpoint": "/search",
        "payload": {
            "query": "automatic background codebase ingestion complex git repo code namespace",
            "top_k": 8,
            "namespaces": ["codex"],
        },
        "must_include_any": ["codebase-auto-ingest.py", "SM_AUTO_INGEST", "background codebase ingestion"],
        "preferred_namespaces": ["codex"],
    },
    {
        "name": "retrieval latency receipt",
        "endpoint": "/search",
        "payload": {
            "query": "semantic-memory warm retrieval benchmark simple search graph traversal latency receipt",
            "top_k": 8,
            "namespaces": ["codex"],
        },
        "must_include_any": ["0.302ms", "warm_simple_search_top5", "warm_graph_discord"],
        "preferred_namespaces": ["codex"],
    },
    {
        "name": "cross-agent compatibility",
        "endpoint": "/search",
        "payload": {
            "query": "semantic-memory-mcp shared by Codex Claude Hermes backward compatible agent neutral",
            "top_k": 8,
            "namespaces": ["codex", "infrastructure"],
        },
        "must_include_any": ["backward compatibility", "Claude", "Codex"],
        "preferred_namespaces": ["codex", "infrastructure"],
    },
    {
        "name": "routed synthesis",
        "endpoint": "/search-routed",
        "payload": {
            "query": "summarize semantic-memory Codex plugin architecture warm search graph recall auto ingest",
            "top_k": 8,
            "query_class": "D",
            "namespaces": ["codex", "infrastructure"],
        },
        "must_include_any": ["semantic-memory", "Codex", "warm"],
        "preferred_namespaces": ["codex", "infrastructure"],
    },
]

NOISE_CASES = [
    {
        "name": "broad codex optimization avoids social noise",
        "prompt": "examine and research everything to make this perform as well as possible for codex, a coding agent",
        "forbidden": ["Grok conversation", "Twitter activity", "https://x.com/"],
    }
]


def post(path: str, payload: dict, timeout: int = 10) -> dict:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    return ordered[f] * (c - k) + ordered[c] * (k - f)


def timed_post(path: str, payload: dict) -> tuple[float, dict]:
    start = time.perf_counter_ns()
    result = post(path, payload)
    elapsed = (time.perf_counter_ns() - start) / 1_000_000.0
    return elapsed, result


def text_of_results(results: list[dict]) -> str:
    return "\n".join(str(row.get("content") or "") for row in results)


def namespace_score(results: list[dict], preferred: list[str]) -> float:
    if not results:
        return 0.0
    preferred_set = set(preferred)
    return sum(1 for row in results if row.get("namespace") in preferred_set) / len(results)


def evaluate_search_case(case: dict) -> dict:
    timings: list[float] = []
    last: dict = {}
    for _ in range(5):
        timed_post(case["endpoint"], case["payload"])
    for _ in range(25):
        elapsed, last = timed_post(case["endpoint"], case["payload"])
        timings.append(elapsed)
    results = last.get("results") or []
    haystack = text_of_results(results).lower()
    expected = [item.lower() for item in case["must_include_any"]]
    matched = [item for item in expected if item in haystack]
    top_content = str((results[0] if results else {}).get("content") or "")
    top_hit_matches = any(item in top_content.lower() for item in expected)
    preferred = case.get("preferred_namespaces") or []
    ns_score = namespace_score(results, preferred) if preferred else 1.0
    return {
        "name": case["name"],
        "endpoint": case["endpoint"],
        "payload": case["payload"],
        "passed": bool(matched),
        "matched": matched,
        "expected_any": expected,
        "top_hit_matches": top_hit_matches,
        "namespace_precision": ns_score,
        "result_count": len(results),
        "top_result_id": (results[0] if results else {}).get("result_id"),
        "top_namespace": (results[0] if results else {}).get("namespace"),
        "latency_ms": {
            "n": len(timings),
            "median": statistics.median(timings),
            "p95": percentile(timings, 95),
            "min": min(timings),
            "max": max(timings),
        },
    }


def evaluate_noise_case(case: dict) -> dict:
    script = Path(__file__).resolve().parents[1] / "hooks/memory-recall.py"
    start = time.perf_counter_ns()
    proc = subprocess.run(
        [str(script)],
        input=json.dumps({"prompt": case["prompt"]}) + "\n",
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "SM_AUTO_INGEST": "0"},
    )
    elapsed = (time.perf_counter_ns() - start) / 1_000_000.0
    haystack = proc.stdout
    forbidden = case["forbidden"]
    present = [item for item in forbidden if item.lower() in haystack.lower()]
    return {
        "name": case["name"],
        "surface": "memory-recall hook policy",
        "prompt": case["prompt"],
        "passed": not present,
        "forbidden_present": present,
        "injected": bool(proc.stdout.strip()),
        "latency_ms": elapsed,
    }


def evaluate_graph() -> dict:
    seed = post(
        "/search",
        {"query": "semantic-memory Codex plugin codebase ingestion graph traversal memory routing", "top_k": 20},
    )
    direct_ids = [row["result_id"] for row in seed.get("results") or [] if row.get("result_id")]
    timings: list[float] = []
    last: dict = {}
    for _ in range(5):
        timed_post("/discord", {"direct_ids": direct_ids[:20], "top_k": 20})
    for _ in range(25):
        elapsed, last = timed_post("/discord", {"direct_ids": direct_ids[:20], "top_k": 20})
        timings.append(elapsed)
    return {
        "name": "graph discord direct ids",
        "passed": bool(last.get("ok")) and int(last.get("edges_loaded") or 0) > 0,
        "direct_id_count": len(direct_ids[:20]),
        "edges_loaded": last.get("edges_loaded"),
        "discord_count": len(last.get("discord_results") or []),
        "latency_ms": {
            "n": len(timings),
            "median": statistics.median(timings),
            "p95": percentile(timings, 95),
            "min": min(timings),
            "max": max(timings),
        },
    }


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stats = post("/stats", {})
    search_results = [evaluate_search_case(case) for case in SEARCH_CASES]
    noise_results = [evaluate_noise_case(case) for case in NOISE_CASES]
    graph = evaluate_graph()
    passed = all(row["passed"] for row in search_results + noise_results) and graph["passed"]
    namespace_scores = [row["namespace_precision"] for row in search_results]
    receipt = {
        "receipt_type": "semantic-memory retrieval quality benchmark",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "stats": stats,
        "passed": passed,
        "quality_summary": {
            "search_cases_passed": sum(1 for row in search_results if row["passed"]),
            "search_cases_total": len(search_results),
            "noise_cases_passed": sum(1 for row in noise_results if row["passed"]),
            "noise_cases_total": len(noise_results),
            "mean_namespace_precision": statistics.fmean(namespace_scores) if namespace_scores else 0.0,
            "graph_passed": graph["passed"],
        },
        "search_results": search_results,
        "noise_results": noise_results,
        "graph_result": graph,
    }
    json_path = OUTDIR / f"retrieval-quality-benchmark-{stamp}.json"
    md_path = OUTDIR / f"retrieval-quality-benchmark-{stamp}.md"
    json_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    lines = [
        "# Semantic Memory Retrieval Quality Benchmark Receipt",
        "",
        f"- Created: `{receipt['created_at']}`",
        f"- Store stats: `{stats}`",
        f"- Passed: `{passed}`",
        f"- JSON receipt: `{json_path}`",
        "",
        "| Case | Pass | Top namespace | Namespace precision | Median ms | p95 ms |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for row in search_results:
        lat = row["latency_ms"]
        lines.append(
            f"| `{row['name']}` | {row['passed']} | `{row['top_namespace']}` | "
            f"{row['namespace_precision']:.2f} | {lat['median']:.3f} | {lat['p95']:.3f} |"
        )
    lines.extend(["", "| Noise Case | Pass | Forbidden Present |", "|---|---:|---|"])
    for row in noise_results:
        lines.append(f"| `{row['name']}` | {row['passed']} | `{', '.join(row['forbidden_present'])}` |")
    glat = graph["latency_ms"]
    lines.extend(
        [
            "",
            "## Graph",
            "",
            f"- Passed: `{graph['passed']}`",
            f"- Direct IDs: `{graph['direct_id_count']}`",
            f"- Edges loaded: `{graph['edges_loaded']}`",
            f"- Discord results: `{graph['discord_count']}`",
            f"- Median: `{glat['median']:.3f} ms`, p95: `{glat['p95']:.3f} ms`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(md_path)
    print(json_path)
    print("\n".join(lines))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
