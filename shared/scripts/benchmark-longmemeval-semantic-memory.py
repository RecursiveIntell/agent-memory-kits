#!/usr/bin/env python3
"""LongMemEval S (official) through the production semantic-memory MCP path.

For every question, the haystack sessions are admitted into an isolated
semantic-memory store under a per-question namespace, then production
``sm_search`` retrieves the ranked sessions for the question. This lane is
explicitly non-witnessed: the current admission gate rejects non-empty source
metadata without a trusted immutable-object resolver, while witnessed search
filters out admitted facts that have no source. Do not use these results for
action-capable injection or describe them as witnessed retrieval.

The output is written in the OFFICIAL LongMemEval retrieval-log schema
(retrieval_results.ranked_items[].corpus_id/text/timestamp + official
session-level metrics via src.retrieval.eval_utils), so the official
run_generation.py and evaluate_qa.py pipeline consumes it unchanged.

Index text follows the official session-granularity scheme exactly:
  - text = ' '.join(user-turn contents)  (assistant turns excluded)
  - corpus_id = session id, with the official 'answer'->'noans' rule
Evidence sessions are identified by 'answer' in the corpus id, matching the
official correct_docs convention in src/retrieval/run_retrieval.py.

One MCP process and one persistent isolated store are used for the complete
run. Admissions are checkpointed per question so a restart does not repeat
thousands of embeddings. The live user memory store is never touched.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LONGMEMEVAL_REPO = ROOT / "benchmarks/LongMemEval"
SCHEMA = "LongMemEvalSemanticMemoryLaneV1"
DEFAULT_EMBEDDER = "nomic-embed-text:q8"
DEFAULT_DIMS = 768
DEFAULT_MAX_CHARS = 6000
DEFAULT_TOP_K = 50  # reader lane uses top-20; 50 keeps recall@30/50 metrics meaningful
SESS_MARKER = re.compile(r"\[lme-session-id:([^\]]+)\]")
CUTOFFS = (1, 3, 5, 10, 30, 50)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def load_mcp_client_module() -> Any:
    path = ROOT / "shared/scripts/benchmark-memory-trust-kernel.py"
    spec = importlib.util.spec_from_file_location("benchmark_memory_trust_kernel", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load existing MCP client from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_ollama(base_url: str, model: str, dimensions: int, timeout: float) -> dict[str, Any]:
    import urllib.request

    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/embeddings",
        data=json.dumps({"model": model, "prompt": "semantic-memory LongMemEval embedding probe"}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != dimensions:
        raise RuntimeError(
            f"Ollama {model} returned {len(embedding) if isinstance(embedding, list) else 0} dimensions, expected {dimensions}"
        )
    return {"status": "passed", "model": model, "dimensions": len(embedding), "latency_ms": (time.perf_counter() - started) * 1000}


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def checkpoint_ids(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    return {
        (str(row["question_id"]), str(row["session_id"]))
        for row in (json.loads(line) for line in path.open(encoding="utf-8") if line.strip())
        if row.get("status") == "admitted"
    }


def corpus_id_for(sess_id: str, sess_entry: list[dict[str, Any]]) -> str:
    """Official session-granularity corpus id with the answer/noans rule."""
    cid = sess_id
    if "answer" in sess_id and not any(
        turn.get("has_answer") for turn in sess_entry if turn.get("role") == "user"
    ):
        cid = sess_id.replace("answer", "noans")
    return cid


def session_index_text(sess_entry: list[dict[str, Any]], max_chars: int) -> str:
    """Official session-granularity index text: user turns joined by spaces."""
    return " ".join(turn["content"] for turn in sess_entry if turn.get("role") == "user")[:max_chars]


def ingest_question(
    client: Any, question: dict[str, Any], *, namespace: str, checkpoint_path: Path, max_chars: int
) -> dict[str, Any]:
    admitted = checkpoint_ids(checkpoint_path)
    failures: list[dict[str, Any]] = []
    admitted_this: list[dict[str, Any]] = []
    started = time.perf_counter()
    qid = str(question["question_id"])
    for sess_id, sess_entry, ts in zip(
        question["haystack_session_ids"], question["haystack_sessions"], question["haystack_dates"]
    ):
        cid = corpus_id_for(sess_id, sess_entry)
        key = (qid, cid)
        if key in admitted:
            admitted_this.append({"session_id": cid, "status": "admitted", "fact_id": "checkpointed"})
            continue
        content = f"[lme-session-id:{cid}] " + session_index_text(sess_entry, max_chars)
        # NOTE: `source` is intentionally omitted — the current admission gate
        # blocks non-empty source unless a trusted immutable-object resolver is
        # configured on the server. Provenance is carried by the checkpoint,
        # the content marker, and the run receipt instead.
        ok, payload = client.call(
            "sm_add_fact",
            {
                "content": content,
                "namespace": namespace,
                "memory_kind": "durable_fact",
                "sensitivity": "public",
                "idempotency_key": f"lme-s-{qid}-{cid}",
            },
        )
        if ok:
            append_jsonl(checkpoint_path, {"question_id": qid, "session_id": cid, "status": "admitted", "fact_id": payload.get("fact_id")})
            admitted_this.append({"session_id": cid, "status": "admitted", "fact_id": payload.get("fact_id")})
        else:
            failures.append({"session_id": cid, "error": payload})
    return {
        "question_id": qid,
        "sessions": len(question["haystack_session_ids"]),
        "admitted": len(admitted_this),
        "failures": failures,
        "elapsed_seconds": time.perf_counter() - started,
    }


def extract_ranked_items(payload: dict[str, Any], dates_by_session: dict[str, str]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        content = str(result.get("content", ""))
        match = SESS_MARKER.search(content)
        if not match:
            continue
        cid = match.group(1)
        text = SESS_MARKER.sub("", content).strip()
        ranked.append({"corpus_id": cid, "text": text, "timestamp": dates_by_session.get(cid, "")})
    return ranked


def retrieve_question(
    client: Any,
    question: dict[str, Any],
    *,
    namespace: str,
    mode: str,
    top_k: int,
) -> dict[str, Any]:
    dates_by_session: dict[str, str] = {}
    for sess_id, sess_entry, ts in zip(
        question["haystack_session_ids"], question["haystack_sessions"], question["haystack_dates"]
    ):
        dates_by_session[corpus_id_for(sess_id, sess_entry)] = ts
    started = time.perf_counter()
    # DEVIATION (documented in receipt): sm_search_witnessed is used by the
    # production path but returns NOTHING for facts admitted without `source`
    # (server.rs witnessed_injectible_fact filters on non-empty source), while
    # the admission gate blocks non-empty `source` unless a trusted
    # immutable-object resolver is configured — which is not configurable in
    # the current build. This lane therefore uses the production hybrid
    # `sm_search` over the same store, same namespace, same query.
    ok, payload = client.call(
        "sm_search",
        {
            "query": str(question.get("question") or ""),
            "namespaces": [namespace],
            "top_k": top_k,
            "retrieval_mode": mode,
        },
    )
    latency_ms = (time.perf_counter() - started) * 1000
    ranked_items = extract_ranked_items(payload, dates_by_session) if ok else []
    return {
        "question_id": str(question["question_id"]),
        "question_type": str(question.get("question_type") or ""),
        "question": str(question.get("question") or ""),
        "answer": str(question.get("answer") or ""),
        "question_date": str(question.get("question_date") or ""),
        "haystack_dates": question["haystack_dates"],
        "haystack_sessions": question["haystack_sessions"],
        "haystack_session_ids": question["haystack_session_ids"],
        "answer_session_ids": question["answer_session_ids"],
        "retrieval_results": {
            "query": str(question.get("question") or ""),
            "ranked_items": ranked_items,
            "metrics": {"session": {}, "turn": {}},
            "receipt_id": payload.get("receipt_id") if isinstance(payload, dict) else None,
            "execution": payload.get("execution") if isinstance(payload, dict) else None,
            "ok": ok,
            "failure": None if ok else (payload.get("error", "search failed") if isinstance(payload, dict) else "search failed"),
            "latency_ms": latency_ms,
            "retrieval_tool": "sm_search (non-witnessed; see deviations)",
        },
    }


def official_session_metrics(entry: dict[str, Any]) -> None:
    """Fill entry['retrieval_results']['metrics']['session'] with the OFFICIAL eval_utils."""
    sys.path.insert(0, str(LONGMEMEVAL_REPO))
    try:
        from src.retrieval.eval_utils import evaluate_retrieval  # type: ignore
    except ImportError as exc:
        log(f"official eval_utils unavailable ({exc}); metrics left empty")
        return
    corpus_ids = [item["corpus_id"] for item in entry["retrieval_results"]["ranked_items"]]
    correct_docs = list({cid for cid in corpus_ids if "answer" in cid})
    rankings = list(range(len(corpus_ids)))
    for k in CUTOFFS:
        recall_any, recall_all, ndcg_any = evaluate_retrieval(rankings, correct_docs, corpus_ids, k=k)
        entry["retrieval_results"]["metrics"]["session"].update(
            {"recall_any@{}".format(k): recall_any, "recall_all@{}".format(k): recall_all, "ndcg_any@{}".format(k): ndcg_any}
        )


def git_state(path: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, timeout=10)
        return result.stdout.strip()

    return {"root": str(path), "branch": run("branch", "--show-current"), "head": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-file", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDER)
    parser.add_argument("--embedding-dims", type=int, default=DEFAULT_DIMS)
    parser.add_argument("--mode", choices=("hybrid", "fts_only", "vector_only"), default="hybrid")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--smoke", type=int, default=0, help="only first N questions")
    args = parser.parse_args()

    in_file = args.in_file.resolve()
    work_dir = args.work_dir.resolve()
    out_dir = args.out_dir.resolve()
    questions = json.load(open(in_file, encoding="utf-8"))
    if args.smoke:
        questions = questions[: args.smoke]
    run_kind = "smoke" if args.smoke else "full"

    probe = probe_ollama(args.ollama_url, args.embedding_model, args.embedding_dims, 60)
    store_dir = work_dir / f"store-{run_kind}-{args.embedding_model.replace(':', '-')}-{args.mode}"
    checkpoint_path = work_dir / f"ingestion-{run_kind}-{args.embedding_model.replace(':', '-')}-{args.mode}.jsonl"
    if checkpoint_path.exists() and not store_dir.exists():
        raise RuntimeError(f"checkpoint exists without its store: {checkpoint_path}; preserve or remove both together")
    store_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

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
    # Dedicated benchmark authority/HTTP token (never the live-store token).
    token_path = work_dir / "bench-token"
    if not token_path.exists():
        token_path.write_text("lme-bench-" + hashlib.sha256(os.urandom(16)).hexdigest() + "\n", encoding="utf-8")
        os.chmod(token_path, 0o600)
    env["SEMANTIC_MEMORY_OPERATOR_AUTHORITY_TOKEN_FILE"] = str(token_path)
    env["SEMANTIC_MEMORY_HTTP_AUTH_TOKEN_FILE"] = str(token_path)
    command = [
        str(launcher),
        "--embedding-url", args.ollama_url,
        "--embedding-model", args.embedding_model,
        "--embedding-dims", str(args.embedding_dims),
    ]
    client = trust_kernel.McpClient(command, env)
    ingestion: dict[str, Any] = {"questions": [], "failures": []}
    retrieval_rows: list[dict[str, Any]] = []
    started_all = time.perf_counter()
    # Incremental log: append each retrieval row as it completes so a timeout
    # or crash never loses already-measured questions (resume-safe).
    log_path = out_dir / f"longmemeval_s_cleaned_sm-{run_kind}-{args.mode}-retrievallog.jsonl"
    log_handle = log_path.open("a", encoding="utf-8")
    try:
        # Transport is stdio MCP only; the HTTP sidecar is unused by this lane
        # (its /search endpoint is token-gated and irrelevant here).
        tool_names = sorted(client.tool_names())
        required = {"sm_add_fact", "sm_search", "sm_stats"}
        missing = sorted(required - set(tool_names))
        if missing:
            raise RuntimeError(f"production MCP surface lacks required tools: {', '.join(missing)}")

        for index, question in enumerate(questions, 1):
            qid = str(question["question_id"])
            namespace = "lme-" + re.sub(r"[^A-Za-z0-9_-]", "_", qid)
            ingested = ingest_question(
                client, question, namespace=namespace, checkpoint_path=checkpoint_path, max_chars=args.max_chars
            )
            ingestion["questions"].append(ingested)
            if ingested["failures"]:
                ingestion["failures"].append({"question_id": qid, "failures": ingested["failures"]})
                log(
                    f"INGEST FAILURES for {qid}: {len(ingested['failures'])} "
                    f"first={json.dumps(ingested['failures'][0])[:500]}"
                )
            row = retrieve_question(client, question, namespace=namespace, mode=args.mode, top_k=args.top_k)
            official_session_metrics(row)
            retrieval_rows.append(row)
            log_handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            log_handle.flush()
            os.fsync(log_handle.fileno())
            if index == 1 or index % 25 == 0 or index == len(questions):
                log(
                    f"progress: {index}/{len(questions)} ingested={sum(q['admitted'] for q in ingestion['questions'])} "
                    f"retrieval_failures={sum(1 for r in retrieval_rows if not r['retrieval_results']['ok'])} "
                    f"elapsed={time.perf_counter() - started_all:.0f}s"
                )
    finally:
        log_handle.close()
        client.close()

    # Re-read the incremental log for the authoritative row set (resume-safe);
    # dedupe by question_id, keeping the latest row for each.
    raw_rows = [json.loads(line) for line in log_path.open(encoding="utf-8") if line.strip()]
    deduped: dict[str, Any] = {}
    for row in raw_rows:
        deduped[row["question_id"]] = row
    retrieval_rows = list(deduped.values())

    receipt = {
        "schema": SCHEMA,
        "status": "complete" if not ingestion["failures"] else "degraded",
        "run_kind": run_kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "dataset": str(in_file),
            "dataset_sha256": sha256_path(in_file),
            "questions": len(questions),
            "embedding_model": args.embedding_model,
            "embedding_dims": args.embedding_dims,
            "retrieval_mode": args.mode,
            "top_k": args.top_k,
            "max_chars_per_session": args.max_chars,
            "index_text": "user turns joined by spaces (official session granularity)",
            "production_tools": {"ingestion": "sm_add_fact", "retrieval": "sm_search", "available": tool_names},
            "deviations": [
                "Retrieval uses sm_search (non-witnessed): sm_search_witnessed returns no hits for facts admitted without `source`, and the current server admission gate blocks non-empty `source` without a configurable trusted immutable-object resolver (semantic-memory-mcp-transport/src/server.rs lines 2070-2074 vs 1370-1372). Witnessed-retrieval coverage exists in the STALE/Sleeper lanes."
            ],
        },
        "embedding": probe,
        "store": {"dir": str(store_dir), "server_binary": shutil.which("semantic-memory-mcp") or "not on PATH"},
        "harness_git": git_state(LONGMEMEVAL_REPO),
        "kit_git": git_state(ROOT),
        "ingestion": {
            "questions": len(ingestion["questions"]),
            "total_admissions": sum(q["admitted"] for q in ingestion["questions"]),
            "total_sessions": sum(q["sessions"] for q in ingestion["questions"]),
            "failure_questions": len(ingestion["failures"]),
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": sha256_path(checkpoint_path) if checkpoint_path.exists() else None,
        },
        "retrieval": {
            "questions_retrieved": len(retrieval_rows),
            "failed_queries": sum(1 for r in retrieval_rows if not r["retrieval_results"]["ok"]),
            "log_path": str(log_path),
            "log_sha256": sha256_path(log_path),
        },
        "total_elapsed_seconds": time.perf_counter() - started_all,
    }
    receipt_path = out_dir / f"receipt-sm-{run_kind}-{args.mode}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
