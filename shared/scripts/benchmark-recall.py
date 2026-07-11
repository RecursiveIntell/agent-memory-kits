#!/usr/bin/env python3
"""Receipt-bench-style recall benchmark for the semantic-memory plugin stack.

Loads JSONL fixtures, queries the semantic-memory HTTP /search endpoint,
computes recall@k, nDCG@k, and MRR, then emits an SMBenchmarkReport receipt.
Fails open (exit 0, server_available=false) if the HTTP server is unavailable.
"""
from __future__ import annotations

import argparse
import json
import uuid
import math
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_NAME = "SMBenchmarkReport"


def get_git_commit() -> str:
    """Return the current git commit hash, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


def get_machine_fingerprint() -> str:
    """Return the hostname as a machine fingerprint."""
    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def load_fixtures(fixtures_dir: Path) -> list[dict[str, Any]]:
    """Load all JSONL fixtures from a directory.

    Returns a list of fixture dicts. Raises SystemExit with message mentioning
    'fixtures' if the directory does not exist.
    """
    if not fixtures_dir.is_dir():
        print(
            f"Error: fixtures directory does not exist: {fixtures_dir}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    fixtures: list[dict[str, Any]] = []
    jsonl_files = sorted(fixtures_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(
            f"Error: no .jsonl fixture files found in {fixtures_dir}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    for fpath in jsonl_files:
        for lineno, line in enumerate(fpath.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(
                    f"Warning: skipping bad JSON in {fpath.name}:{lineno}: {exc}",
                    file=sys.stderr,
                )
                continue
            if "query" not in obj or "expected_result_ids" not in obj:
                print(
                    f"Warning: skipping fixture {fpath.name}:{lineno} missing required fields",
                    file=sys.stderr,
                )
                continue
            fixtures.append(obj)

    if not fixtures:
        print(
            f"Error: no valid fixtures loaded from {fixtures_dir}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return fixtures


def check_server_available(base_url: str, timeout: float = 2.0) -> bool:
    """Check if the semantic-memory HTTP server is reachable."""
    try:
        req = urllib.request.Request(
            base_url + "/health",
            method="GET",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except (urllib.error.URLError, OSError, ConnectionError, TimeoutError):
        pass
    # Try a POST to /search with a trivial query as a fallback health check
    try:
        body = json.dumps({"query": "health-check", "top_k": 1}).encode("utf-8")
        req = urllib.request.Request(
            base_url + "/search",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except (urllib.error.URLError, OSError, ConnectionError, TimeoutError):
        return False


def search(
    base_url: str, query: str, top_k: int, namespace: str | None = None, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """Call the semantic-memory /search endpoint and return results list."""
    payload: dict[str, Any] = {"query": query, "top_k": top_k}
    if namespace:
        payload["namespaces"] = [namespace]
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url + "/search",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    return []


def normalize_result_id(value: str) -> str:
    """Normalize stable HTTP/MCP IDs (e.g. fact:<uuid>) to fixture IDs."""
    return value.split(":", 1)[1] if value.startswith(("fact:", "chunk:")) else value


def extract_result_ids(results: list[dict[str, Any]]) -> list[str]:
    """Extract and normalize result IDs from search results."""
    ids: list[str] = []
    for r in results:
        for key in ("result_id", "id", "fact_id", "uuid", "_id"):
            val = r.get(key)
            if val:
                ids.append(normalize_result_id(str(val)))
                break
        else:
            ids.append("")
    return ids


def compute_recall_at_k(
    expected_ids: list[str], result_ids: list[str], k: int
) -> float:
    """Recall@k: fraction of expected_ids found in the top-k results."""
    if not expected_ids:
        return 0.0
    top_k_ids = {normalize_result_id(rid) for rid in result_ids[:k]}
    hits = sum(1 for eid in expected_ids if normalize_result_id(eid) in top_k_ids)
    return hits / len(expected_ids)


def compute_ndcg_at_k(
    expected_ids: list[str], result_ids: list[str], k: int
) -> float:
    """nDCG@k: normalized discounted cumulative gain.

    Treats each expected ID as a relevant result (binary relevance).
    DCG = sum(rel_i / log2(i+1)) for i=1..k
    IDCG = ideal DCG (all relevant items at the top)
    """
    if not expected_ids:
        return 0.0
    expected_set = set(expected_ids)

    dcg = 0.0
    for i, rid in enumerate(result_ids[:k]):
        if rid in expected_set:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because i is 0-indexed, rank starts at 1

    # Ideal DCG: all expected items appear first
    num_relevant = min(len(expected_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(num_relevant))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def compute_mrr(
    expected_ids: list[str], result_ids: list[str], k: int
) -> float:
    """MRR (mean reciprocal rank): 1/rank of first relevant result, 0 if none in top-k."""
    expected_set = set(expected_ids)
    for i, rid in enumerate(result_ids[:k]):
        if rid in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def build_receipt(
    fixtures: list[dict[str, Any]],
    per_fixture: list[dict[str, Any]],
    server_available: bool,
    top_k_default: int,
) -> dict[str, Any]:
    """Build the SMBenchmarkReport receipt dict."""
    n = len(per_fixture)
    recall_avg = sum(pf["recall"] for pf in per_fixture) / n if n else 0.0
    ndcg_avg = sum(pf["ndcg"] for pf in per_fixture) / n if n else 0.0
    mrr_avg = sum(pf["mrr"] for pf in per_fixture) / n if n else 0.0

    return {
        "schema": SCHEMA_NAME,
        "trace_id": f"trace:benchmark-recall:{uuid.uuid4().hex[:16]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "machine_fingerprint": get_machine_fingerprint(),
        "fixtures_used": len(fixtures),
        "server_available": server_available,
        "recall_at_k": round(recall_avg, 6),
        "ndcg_at_k": round(ndcg_avg, 6),
        "mrr": round(mrr_avg, 6),
        "per_fixture": per_fixture,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Receipt-bench-style recall benchmark for semantic-memory."
    )
    ap.add_argument("--fixtures-dir", required=True, help="Directory containing .jsonl fixture files")
    ap.add_argument("--out", required=True, help="Output path for the JSON receipt")
    ap.add_argument("--top-k", type=int, default=10, help="Default top-k for search (default: 10)")
    ap.add_argument("--write-claim-ledger", action="store_true", help="Write benchmark receipt to claim-ledger MCP if available")
    args = ap.parse_args()

    fixtures_dir = Path(args.fixtures_dir)
    out_path = Path(args.out)

    # Load fixtures — exits with code 1 if directory missing or no valid fixtures
    fixtures = load_fixtures(fixtures_dir)

    # Determine server URL
    port = os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", "1739")
    base_url = os.environ.get("SEMANTIC_MEMORY_HTTP_URL", f"http://127.0.0.1:{port}")

    # Check server availability
    server_available = check_server_available(base_url)

    per_fixture: list[dict[str, Any]] = []

    if server_available:
        for fx in fixtures:
            query = fx["query"]
            expected_ids = fx["expected_result_ids"]
            ns = fx.get("namespace")
            k = fx.get("top_k", args.top_k)

            try:
                results = search(base_url, query, k, namespace=ns)
            except Exception as exc:
                print(f"Warning: search failed for query '{query}': {exc}", file=sys.stderr)
                results = []

            result_ids = extract_result_ids(results)

            recall = compute_recall_at_k(expected_ids, result_ids, k)
            ndcg = compute_ndcg_at_k(expected_ids, result_ids, k)
            mrr = compute_mrr(expected_ids, result_ids, k)

            per_fixture.append({
                "query": query,
                "recall": round(recall, 6),
                "ndcg": round(ndcg, 6),
                "mrr": round(mrr, 6),
                "results_count": len(results),
            })
    else:
        # Server unavailable: emit per_fixture with zeroed metrics
        for fx in fixtures:
            per_fixture.append({
                "query": fx["query"],
                "recall": 0.0,
                "ndcg": 0.0,
                "mrr": 0.0,
                "results_count": 0,
            })

    receipt = build_receipt(fixtures, per_fixture, server_available, args.top_k)

    # Write receipt
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    print(f"Receipt written to {out_path}")
    print(f"  schema: {receipt['schema']}")
    print(f"  server_available: {server_available}")
    print(f"  fixtures_used: {receipt['fixtures_used']}")
    print(f"  recall@k: {receipt['recall_at_k']:.4f}  nDCG@k: {receipt['ndcg_at_k']:.4f}  MRR: {receipt['mrr']:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())