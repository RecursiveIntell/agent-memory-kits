#!/usr/bin/env python3
"""Benchmark semantic-memory retrieval ranking on official BEIR Scifact qrels.

The runner downloads the public Scifact archive, writes document text through
the production ``sm_add_fact`` MCP API, and retrieves through production
``sm_search_witnessed``.  One MCP process and one persistent isolated store are
used for the complete run.  Successful admissions are checkpointed so a
restart does not repeat thousands of embeddings.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "BeirScifactRankingBenchmarkV1"
SCHEMA_PATH = ROOT / "shared/fixtures/schemas/beir-scifact-ranking-receipt.schema.json"
SCIFACT_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
DEFAULT_MODEL = "all-minilm:latest"
DEFAULT_DIMS = 384
DEFAULT_MAX_CHARS = 700
EXPECTED_CORPUS_DOCS = 5_183
DOC_MARKER = re.compile(r"\[beir-scifact-doc-id:([^\]]+)\]")


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"expected object at {path}:{line_number}")
            rows.append(value)
    return rows


def load_qrels(path: Path) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    """Parse positive official qrels without collapsing multi-relevant queries."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip().split("\t")[:3] != ["query-id", "corpus-id", "score"]:
        raise ValueError("qrels must start with query-id, corpus-id, score header")
    qrels: dict[str, dict[str, int]] = {}
    for line_number, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 3:
            raise ValueError(f"malformed qrel at {path}:{line_number}")
        query_id, doc_id = fields[:2]
        try:
            relevance = int(fields[2])
        except ValueError as exc:
            raise ValueError(f"non-integer qrel at {path}:{line_number}") from exc
        if relevance > 0:
            qrels.setdefault(query_id, {})[doc_id] = relevance
    return qrels, {
        "path": str(path),
        "sha256": sha256_path(path),
        "query_count": len(qrels),
        "qrels_count": sum(len(documents) for documents in qrels.values()),
    }


def score_query(
    relevant: dict[str, int], ranked_doc_ids: list[str], *, cutoffs: tuple[int, ...] = (1, 5, 10)
) -> dict[str, Any]:
    """Compute standard binary recall/success/MRR/MAP and graded nDCG."""
    relevant_ids = set(relevant)
    recall: dict[str, float] = {}
    success: dict[str, float] = {}
    for cutoff in cutoffs:
        hits = relevant_ids.intersection(ranked_doc_ids[:cutoff])
        recall[str(cutoff)] = len(hits) / len(relevant_ids) if relevant_ids else 0.0
        success[str(cutoff)] = float(bool(hits))

    first_rank = next(
        (rank for rank, doc_id in enumerate(ranked_doc_ids[:10], 1) if doc_id in relevant_ids),
        None,
    )
    precision_sum = 0.0
    hits = 0
    seen: set[str] = set()
    for rank, doc_id in enumerate(ranked_doc_ids[:10], 1):
        if doc_id in relevant_ids and doc_id not in seen:
            seen.add(doc_id)
            hits += 1
            precision_sum += hits / rank
    ap_denominator = min(len(relevant_ids), 10)

    dcg = sum(
        (2 ** relevant.get(doc_id, 0) - 1) / math.log2(rank + 1)
        for rank, doc_id in enumerate(ranked_doc_ids[:10], 1)
        if doc_id in relevant
    )
    ideal_relevances = sorted(relevant.values(), reverse=True)[:10]
    idcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal_relevances, 1))
    return {
        "ndcg_at_10": dcg / idcg if idcg else 0.0,
        "recall_at_k": recall,
        "mrr_at_10": 1.0 / first_rank if first_rank else 0.0,
        "map_at_10": precision_sum / ap_denominator if ap_denominator else 0.0,
        "success_at_k": success,
    }


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def aggregate_query_rows(
    rows: list[dict[str, Any]], *, cutoffs: tuple[int, ...] = (1, 5, 10)
) -> dict[str, Any]:
    """Macro-average every official query; failed queries remain zero-valued rows."""
    count = len(rows)
    metrics = [row["metrics"] for row in rows]
    mean = lambda values: sum(values) / count if count else None
    latencies = [float(row["latency_ms"]) for row in rows if isinstance(row.get("latency_ms"), (int, float))]
    return {
        "query_count": count,
        "qrels_count": sum(int(row.get("qrels_count", 0)) for row in rows),
        "failures": sum(row.get("status") != "measured" for row in rows),
        "ndcg_at_10": mean([item["ndcg_at_10"] for item in metrics]),
        "recall_at_k": {str(k): mean([item["recall_at_k"][str(k)] for item in metrics]) for k in cutoffs},
        "mrr_at_10": mean([item["mrr_at_10"] for item in metrics]),
        "map_at_10": mean([item["map_at_10"] for item in metrics]),
        "success_at_k": {str(k): mean([item["success_at_k"][str(k)] for item in metrics]) for k in cutoffs},
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "mean": statistics.fmean(latencies) if latencies else None,
        },
    }


def download_and_extract(work_dir: Path) -> tuple[Path, dict[str, Any]]:
    data_dir = work_dir / "data"
    archive_path = data_dir / "scifact.zip"
    dataset_dir = data_dir / "scifact"
    data_dir.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        log(f"downloading {SCIFACT_URL}")
        urllib.request.urlretrieve(SCIFACT_URL, archive_path)
    if not (dataset_dir / "corpus.jsonl").is_file():
        log(f"extracting {archive_path}")
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(data_dir)
    required = [dataset_dir / "corpus.jsonl", dataset_dir / "queries.jsonl", dataset_dir / "qrels/test.tsv"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Scifact archive is incomplete: {', '.join(missing)}")
    return dataset_dir, {
        "source_url": SCIFACT_URL,
        "archive": {"path": str(archive_path), "sha256": sha256_path(archive_path)},
        "corpus": {"path": str(required[0]), "sha256": sha256_path(required[0])},
        "queries": {"path": str(required[1]), "sha256": sha256_path(required[1])},
    }


def document_content(row: dict[str, Any], max_chars: int) -> str:
    doc_id = str(row["_id"])
    marker = f"[beir-scifact-doc-id:{doc_id}]"
    title = str(row.get("title") or "").strip()
    body = str(row.get("text") or "").strip()
    semantic_text = "\n".join(part for part in (title, body) if part)[:max_chars]
    return "\n".join(part for part in (marker, semantic_text) if part)


def extract_doc_ids(payload: dict[str, Any]) -> list[str]:
    """Extract stable public doc IDs while preserving production score order."""
    identifiers: list[str] = []
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        metadata = result.get("metadata")
        metadata_id = metadata.get("beir_scifact_doc_id") if isinstance(metadata, dict) else None
        if metadata_id is not None:
            identifiers.append(str(metadata_id))
            continue
        match = DOC_MARKER.search(str(result.get("content", "")))
        if match:
            identifiers.append(match.group(1))
    return identifiers


def select_query_ids(qrels: dict[str, dict[str, int]], query_split: str) -> list[str]:
    ordered = sorted(qrels)
    if query_split == "calibration":
        return ordered[:100]
    if query_split == "heldout":
        return ordered[100:]
    if query_split == "all":
        return ordered
    raise ValueError(f"unknown query split: {query_split}")


def git_state(path: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    status = run("status", "--porcelain")
    return {"path": str(path), "commit": run("rev-parse", "HEAD"), "dirty": bool(status)}


def resolved_semantic_memory_binary() -> Path:
    candidates = [
        os.environ.get("SEMANTIC_MEMORY_MCP_BIN"),
        str(Path.home() / "Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp"),
        str(Path.home() / ".local/bin/semantic-memory-mcp"),
        shutil.which("semantic-memory-mcp"),
        str(Path.home() / ".cargo/bin/semantic-memory-mcp"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise RuntimeError("semantic-memory-mcp binary cannot be resolved")


def load_mcp_client_module() -> Any:
    path = ROOT / "shared/scripts/benchmark-memory-trust-kernel.py"
    spec = importlib.util.spec_from_file_location("benchmark_memory_trust_kernel", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load existing MCP client from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_ollama(base_url: str, model: str, dimensions: int, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/embeddings",
        data=json.dumps({"model": model, "prompt": "semantic-memory Scifact embedding probe"}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != dimensions:
        raise RuntimeError(f"Ollama {model} returned {len(embedding) if isinstance(embedding, list) else 0} dimensions, expected {dimensions}")
    return {"status": "passed", "model": model, "dimensions": len(embedding), "latency_ms": (time.perf_counter() - started) * 1000}


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def checkpoint_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {str(row["doc_id"]) for row in read_jsonl(path) if row.get("status") == "admitted"}


def checkpoint_timing(path: Path) -> dict[str, Any] | None:
    """Preserve the durable checkpoint's initial write span when statx exposes birth time."""
    if not path.exists():
        return None
    result = subprocess.run(["stat", "-c", "%W", str(path)], text=True, capture_output=True, timeout=5)
    try:
        created = float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except ValueError:
        created = 0.0
    completed = path.stat().st_mtime
    if created <= 0 or completed < created:
        return None
    return {
        "created_at": datetime.fromtimestamp(created, timezone.utc).isoformat(),
        "last_admission_at": datetime.fromtimestamp(completed, timezone.utc).isoformat(),
        "initial_write_span_seconds": completed - created,
        "source": "filesystem birth-to-last-modification timestamps",
    }


def ingest_documents(
    client: Any,
    documents: list[dict[str, Any]],
    *,
    namespace: str,
    checkpoint_path: Path,
    max_chars: int,
) -> dict[str, Any]:
    admitted_ids = checkpoint_ids(checkpoint_path)
    failures: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, document in enumerate(documents, 1):
        doc_id = str(document["_id"])
        if doc_id in admitted_ids:
            continue
        content = document_content(document, max_chars)
        ok, payload = client.call(
            "sm_add_fact",
            {
                "content": content,
                "namespace": namespace,
                "memory_kind": "durable_fact",
                "sensitivity": "public",
                "source": f"BEIR Scifact corpus document {doc_id}",
                "idempotency_key": "beir-scifact-doc-" + doc_id,
            },
        )
        if ok:
            append_jsonl(checkpoint_path, {"doc_id": doc_id, "status": "admitted", "fact_id": payload.get("fact_id")})
            admitted_ids.add(doc_id)
        else:
            failures.append({"doc_id": doc_id, "error": payload})
        if index == 1 or index % 100 == 0 or index == len(documents):
            elapsed = max(time.perf_counter() - started, 0.001)
            log(f"ingestion: {index}/{len(documents)} checkpointed={len(admitted_ids)} rate={index/elapsed:.2f}/s failures={len(failures)}")
    return {
        "requested_docs": len(documents),
        "checkpointed_docs": len(admitted_ids.intersection({str(row["_id"]) for row in documents})),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": sha256_path(checkpoint_path) if checkpoint_path.exists() else None,
        "failures": failures,
        "active_pass_elapsed_seconds": time.perf_counter() - started,
        "checkpoint_timing": checkpoint_timing(checkpoint_path),
    }


def zero_metrics(cutoffs: tuple[int, ...]) -> dict[str, Any]:
    return score_query({}, [], cutoffs=cutoffs)


def retrieve_queries(
    client: Any,
    queries: list[dict[str, Any]],
    qrels: dict[str, dict[str, int]],
    *,
    namespace: str,
    mode: str,
    cutoffs: tuple[int, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, query in enumerate(queries, 1):
        query_id = str(query["_id"])
        relevant = qrels[query_id]
        started = time.perf_counter()
        ok, payload = client.call(
            "sm_search_witnessed",
            {
                "query": str(query.get("text") or ""),
                "namespaces": [namespace],
                "top_k": 10,
                "retrieval_mode": mode,
            },
        )
        latency_ms = (time.perf_counter() - started) * 1000
        ranked_ids = extract_doc_ids(payload) if ok else []
        failure = None
        if not ok:
            failure = payload.get("error", "MCP retrieval failed")
        elif len(ranked_ids) != len(payload.get("results", [])):
            failure = "one or more returned results lacked a stable Scifact doc-id marker"
        metrics = score_query(relevant, ranked_ids, cutoffs=cutoffs) if failure is None else zero_metrics(cutoffs)
        rows.append(
            {
                "schema": SCHEMA,
                "mode": mode,
                "query_id": query_id,
                "query": str(query.get("text") or ""),
                "relevant_doc_ids": sorted(relevant),
                "qrels_count": len(relevant),
                "ranked_doc_ids": ranked_ids,
                "returned_results": len(payload.get("results", [])) if isinstance(payload, dict) else 0,
                "receipt_id": payload.get("receipt_id") if isinstance(payload, dict) else None,
                "retrieval_execution": payload.get("execution") if isinstance(payload, dict) else None,
                "stage_outcomes": payload.get("stage_outcomes") if isinstance(payload, dict) else None,
                "status": "measured" if failure is None else "failed",
                "failure": failure,
                "latency_ms": latency_ms,
                "metrics": metrics,
            }
        )
        if index == 1 or index % 25 == 0 or index == len(queries):
            log(f"retrieval: {index}/{len(queries)} failures={sum(row['status'] != 'measured' for row in rows)}")
    return rows


def select_smoke_documents(
    corpus: list[dict[str, Any]], query_ids: list[str], qrels: dict[str, dict[str, int]], limit: int = 20
) -> list[dict[str, Any]]:
    required = {doc_id for query_id in query_ids for doc_id in qrels[query_id]}
    if len(required) > limit:
        raise ValueError(f"first smoke queries require {len(required)} relevant docs, exceeding {limit}-doc smoke bound")
    selected = [row for row in corpus if str(row["_id"]) in required]
    selected_ids = {str(row["_id"]) for row in selected}
    selected.extend(row for row in corpus if str(row["_id"]) not in selected_ids and len(selected) < limit)
    return selected


def validate_receipt(receipt: dict[str, Any], schema_path: Path = SCHEMA_PATH) -> None:
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(receipt, schema)


def render_report(receipt: dict[str, Any]) -> str:
    selected_mode = receipt["config"].get("retrieval_mode", "hybrid")
    mode = receipt["modes"][selected_mode]
    metrics = mode["metrics"]
    latency = metrics["latency_ms"]
    lines = [
        "# Semantic-Memory BEIR Scifact Retrieval Ranking",
        "",
        f"- Status: **{receipt['status']}**",
        f"- Run kind: `{receipt['run_kind']}`",
        f"- Corpus documents: {receipt['dataset']['corpus_doc_count']:,}",
        f"- Official test queries: {metrics['query_count']}",
        f"- Positive qrels: {metrics['qrels_count']}",
        f"- Embedder: Ollama `{receipt['embedding']['model']}`, {receipt['embedding']['dimensions']} dimensions",
        f"- Production path: `sm_add_fact` -> `sm_search_witnessed`",
        "",
        f"## {selected_mode} results",
        "",
        "| nDCG@10 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | MAP@10 | Success@1 | Success@5 | Success@10 | Failures |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| " + " | ".join(
            f"{value:.6f}" if isinstance(value, float) else str(value)
            for value in (
                metrics["ndcg_at_10"], metrics["recall_at_k"]["1"], metrics["recall_at_k"]["5"],
                metrics["recall_at_k"]["10"], metrics["mrr_at_10"], metrics["map_at_10"],
                metrics["success_at_k"]["1"], metrics["success_at_k"]["5"], metrics["success_at_k"]["10"],
                metrics["failures"],
            )
        ) + " |",
        "",
        f"Latency: p50 `{latency['p50']:.3f} ms`, p95 `{latency['p95']:.3f} ms`, mean `{latency['mean']:.3f} ms`.",
        "",
        "## Mode boundary",
        "",
        *[
            f"- {name}: **{details['status']}**"
            + (f" — {details['reason']}" if details.get("reason") else "")
            for name, details in receipt["modes"].items()
        ],
        "",
        "## Provenance and artifacts",
        "",
        f"- Corpus SHA-256: `{receipt['dataset']['corpus']['sha256']}`",
        f"- Test qrels SHA-256: `{receipt['dataset']['qrels']['sha256']}`",
        f"- Per-query JSONL: `{receipt['artifacts']['per_query']['path']}` (`{receipt['artifacts']['per_query']['sha256']}`)",
        f"- Store: `{receipt['execution']['store_path']}`",
        f"- Ingestion checkpoint: `{receipt['ingestion']['checkpoint_path']}`",
        "",
        "## Exact command",
        "",
        "```bash",
        receipt["execution"]["command"],
        "```",
        "",
        "## Claim boundary",
        "",
        "These are ordinary retrieval-ranking measurements on public BEIR Scifact test qrels. No competitor comparison, superiority claim, hidden-label feature, query-copy distractor, or test-qrel tuning is included.",
        "",
    ]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    work_dir = args.work_dir.resolve()
    output_dir = args.output_dir.resolve()
    dataset_dir, dataset_source = download_and_extract(work_dir)
    corpus = read_jsonl(dataset_dir / "corpus.jsonl")
    all_queries = read_jsonl(dataset_dir / "queries.jsonl")
    qrels, qrels_source = load_qrels(dataset_dir / "qrels/test.tsv")
    if len(corpus) != EXPECTED_CORPUS_DOCS:
        raise RuntimeError(f"official Scifact corpus must contain {EXPECTED_CORPUS_DOCS} docs, found {len(corpus)}")
    queries_by_id = {str(row["_id"]): row for row in all_queries}
    missing_queries = sorted(set(qrels) - set(queries_by_id))
    if missing_queries:
        raise RuntimeError(f"qrels reference missing queries: {missing_queries[:5]}")
    query_ids = select_query_ids(qrels, args.query_split)
    if args.smoke:
        query_ids = query_ids[:5]
        documents = select_smoke_documents(corpus, query_ids, qrels, 20)
        run_kind = "smoke"
    else:
        documents = corpus
        run_kind = "full"
    queries = [queries_by_id[query_id] for query_id in query_ids]

    probe = probe_ollama(args.ollama_url, args.model, args.dimensions, args.timeout)
    namespace = args.namespace + ("-smoke" if args.smoke else "")
    store_dir = work_dir / f"store-{run_kind}-{args.model.replace(':', '-')}-{args.max_chars}"
    checkpoint_path = work_dir / f"ingestion-{run_kind}-{args.model.replace(':', '-')}-{args.max_chars}.jsonl"
    if checkpoint_path.exists() and not store_dir.exists():
        raise RuntimeError(f"checkpoint exists without its store: {checkpoint_path}; preserve or remove both together")
    store_dir.mkdir(parents=True, exist_ok=True)

    trust_kernel = load_mcp_client_module()
    port = trust_kernel.free_port()
    endpoint = f"http://127.0.0.1:{port}"
    launcher = ROOT / "shared/scripts/run-server.sh"
    if not launcher.is_file() or not shutil.which("bash"):
        raise RuntimeError("documented semantic-memory launcher is unavailable")
    env = {
        **os.environ,
        "SEMANTIC_MEMORY_DIR": str(store_dir),
        "SEMANTIC_MEMORY_HTTP_PORT": str(port),
        "SEMANTIC_MEMORY_EMBEDDER": "ollama",
        "SEMANTIC_MEMORY_TOOL_PROFILE": "full",
        "RUST_LOG": "error",
    }
    command = [
        str(launcher),
        "--embedding-url", args.ollama_url,
        "--embedding-model", args.model,
        "--embedding-dims", str(args.dimensions),
    ]
    runtime_binary = resolved_semantic_memory_binary()
    client = trust_kernel.McpClient(command, env)
    started = time.perf_counter()
    try:
        for _ in range(80):
            if trust_kernel.endpoint_available(endpoint):
                break
            time.sleep(0.15)
        if not trust_kernel.endpoint_available(endpoint):
            raise RuntimeError("isolated semantic-memory MCP/HTTP service did not become available")
        tool_names = sorted(client.tool_names())
        required = {"sm_add_fact", "sm_search_witnessed", "sm_stats"}
        missing = sorted(required - set(tool_names))
        if missing:
            raise RuntimeError(f"production MCP surface lacks required tools: {', '.join(missing)}")
        ingestion = ingest_documents(
            client, documents, namespace=namespace, checkpoint_path=checkpoint_path, max_chars=args.max_chars
        )
        if ingestion["failures"] or ingestion["checkpointed_docs"] != len(documents):
            raise RuntimeError(f"ingestion incomplete: {ingestion['checkpointed_docs']}/{len(documents)} with {len(ingestion['failures'])} failures")
        stats_ok, stats = client.call("sm_stats", {})
        if not stats_ok:
            raise RuntimeError(f"sm_stats failed after ingestion: {stats}")
        rows = retrieve_queries(
            client, queries, qrels, namespace=namespace, mode=args.mode, cutoffs=(1, 5, 10)
        )
    finally:
        client.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "smoke-" if args.smoke else f"{args.query_split}-{args.mode}-"
    per_query_path = output_dir / f"{prefix}per-query.jsonl"
    per_query_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    metrics = aggregate_query_rows(rows, cutoffs=(1, 5, 10))
    not_selected = "not selected for this mode-separated run"
    exact_command = ["python3", str(Path(__file__).relative_to(ROOT))]
    if args.smoke:
        exact_command.append("--smoke")
    exact_command.extend([
        "--work-dir", str(args.work_dir), "--output-dir", str(args.output_dir),
        "--model", args.model, "--dimensions", str(args.dimensions),
        "--max-chars", str(args.max_chars),
        "--mode", args.mode, "--query-split", args.query_split,
    ])
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "measured" if metrics["failures"] == 0 else "failed",
        "run_kind": run_kind,
        "dataset": {
            **dataset_source,
            "name": "BEIR Scifact official corpus/test qrels",
            "corpus_doc_count": len(documents),
            "official_full_corpus_doc_count": len(corpus),
            "qrels": qrels_source,
            "selected_test_queries": len(queries),
        },
        "embedding": {"backend": "ollama", "model": args.model, "dimensions": args.dimensions, "max_document_chars": args.max_chars, "probe": probe},
        "repositories": {
            "agent_memory_kits": git_state(ROOT),
            "semantic_memory": git_state(Path.home() / "Coding/Libraries/semantic-memory"),
            "semantic_memory_mcp": git_state(Path.home() / "Coding/Libraries/semantic-memory-mcp"),
        },
        "execution": {
            "launcher": str(launcher),
            "launcher_sha256": sha256_path(launcher),
            "runner_sha256": sha256_path(Path(__file__)),
            "receipt_schema_path": str(SCHEMA_PATH),
            "receipt_schema_sha256": sha256_path(SCHEMA_PATH),
            "launcher_command": command,
            "runtime_binary": {"path": str(runtime_binary), "sha256": sha256_path(runtime_binary)},
            "command": " ".join(exact_command),
            "single_service": True,
            "store_path": str(store_dir),
            "namespace": namespace,
            "active_receipt_pass_elapsed_seconds": time.perf_counter() - started,
            "production_tools": {"ingestion": "sm_add_fact", "retrieval": "sm_search_witnessed", "available": tool_names},
            "stats": stats,
        },
        "ingestion": ingestion,
        "modes": {
            mode: ({"status": "measured", "metrics": metrics} if mode == args.mode else {"status": "not_selected", "reason": not_selected})
            for mode in ("hybrid", "fts_only", "vector_only")
        },
        "config": {"top_k": 10, "cutoffs": [1, 5, 10], "query_split": args.query_split, "retrieval_mode": args.mode, "relevance": "positive official qrels", "metric_averaging": "macro over official qrel queries", "doc_id_marker": "[beir-scifact-doc-id:<corpus-id>]"},
        "artifacts": {"per_query": {"path": str(per_query_path), "sha256": sha256_path(per_query_path), "rows": len(rows)}},
        "claim_boundary": "ordinary retrieval ranking only; no competitor comparison or superiority claim",
    }
    validate_receipt(receipt)
    aggregate_path = output_dir / f"{prefix}aggregate.json"
    report_path = output_dir / f"{prefix}report.md"
    aggregate_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(receipt), encoding="utf-8")
    log(f"wrote {aggregate_path}")
    log(f"wrote {per_query_path}")
    log(f"wrote {report_path}")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".bench-data/beir-scifact-ranking")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/benchmarks/beir-scifact-ranking")
    parser.add_argument("--smoke", action="store_true", help="Run the predeclared 20-document/5-query technical smoke.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dimensions", type=int, default=DEFAULT_DIMS)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--namespace", default="benchmark-beir-scifact-test-v1")
    parser.add_argument("--mode", choices=("hybrid", "fts_only", "vector_only"), default="hybrid")
    parser.add_argument("--query-split", choices=("calibration", "heldout", "all"), default="all")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
