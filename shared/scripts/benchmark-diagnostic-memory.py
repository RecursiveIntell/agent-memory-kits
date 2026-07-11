#!/usr/bin/env python3
"""Local, receipt-backed adapters for diagnostic memory benchmarks.

The named research benchmarks are *adapter families*, not bundled datasets.
This runner ships only tiny CC0 deterministic fixtures.  It never downloads,
copies, or labels an unavailable upstream dataset as a pass.  Point an adapter
at an independently obtained local fixture with ``--adapter-fixture`` to run
it; a missing path is emitted as ``not_tested`` in the receipt.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "DiagnosticMemoryBenchmarkV1"
FIXTURE_SCHEMA = "DiagnosticMemoryFixtureBundleV1"
ADAPTER_FIXTURE_SCHEMA = "DiagnosticMemoryAdapterFixtureV1"
MEMORY_INFLUENCE_SCHEMA = "MemoryInfluenceReceiptV1"
MEMORY_INFLUENCE_FIXTURE_SCHEMA = "MemoryInfluenceFixtureBundleV1"
ADAPTER_IDS = (
    "stale",
    "atma_ltp",
    "memtrace",
    "memconflict",
    "trustmem_halumem",
    "mpbench_ghostwriter",
    "gatemem_groupmembench",
    "memoryarena",
)
COMPETITOR_IDS = ("mem0", "graphiti_zep", "letta", "langmem")
COMPETITOR_STALE_SMOKE_INDICES = (*range(10), *range(100, 110))
COMPETITOR_PINS = {
    "mem0": {
        "name": "Mem0",
        "repository": "https://github.com/mem0ai/mem0",
        "commit": "c9af55986e4a31aa98931b6b909d5639e9b2013a",
        "package": "mem0ai",
        "version": "2.0.11",
        "license": "Apache-2.0",
        "license_sha256": "sha256:0bbcbe931c353293a2fafce08326181dfeea0e568c566afd4ce8337a70f5e219",
        "package_manifest_sha256": "sha256:faebb337990d1c0cfe83494e59ffa419fdf47c0690ebcc259470d6dc4aba0186",
    },
    "graphiti_zep": {
        "name": "Graphiti / Zep",
        "repository": "https://github.com/getzep/graphiti",
        "commit": "526dcad7a300f3c5c506ff96a68bcdc7ca9f97ed",
        "package": "graphiti-core",
        "version": "0.29.2",
        "license": "Apache-2.0",
        "license_sha256": "sha256:2825300b20d7b951209835a4a331f29e24725a39d65168e4b831df53aa372650",
        "package_manifest_sha256": "sha256:e8157e9b9c84a01b86e4e02e6cdc586b6e42e61d3c1612d1bb5aeef2f8309b44",
    },
    "letta": {
        "name": "Letta",
        "repository": "https://github.com/letta-ai/letta",
        "commit": "b76da9092518cbaa2d09042e52fdcbde69243e18",
        "package": "letta",
        "version": "0.16.8",
        "license": "Apache-2.0",
        "license_sha256": "sha256:984c6db99fc6609803108dfc196762118662cd94b82a456dd9217583f18f3612",
        "package_manifest_sha256": "sha256:ba86147a334a4900962b260d1912e263e011e8698377327b9f1a8fd943540c3e",
    },
    "langmem": {
        "name": "LangMem",
        "repository": "https://github.com/langchain-ai/langmem",
        "commit": "c01e273b94aa4c06e41d0ed1ccce0db17de2bc11",
        "package": "langmem",
        "version": "0.0.30",
        "license": "MIT",
        "license_sha256": "sha256:98af1351ea856e008c835bc89a312905960a318072f950732bf346c741027c7d",
        "package_manifest_sha256": "sha256:6a964d268d23b8860c848b7b23f2dc6998204eaa0eb28cfe2d404359eb51611a",
    },
}
BASELINE_CELLS = (
    "no_memory",
    "full_context",
    "bm25",
    "dense",
    "exact_hybrid",
    "witnessed_hybrid",
    "state_resolved",
)
PHASES = (
    "ingestion",
    "extraction",
    "transition_proposal",
    "verification",
    "commit",
    "indexing",
    "retrieval",
    "rerank",
    "state_resolution",
    "evidence_sufficiency",
    "admission",
    "answer_use",
    "tool_arguments",
    "testimony",
    "forgetting",
)
MEMORY_INFLUENCE_CELLS = (
    "no_memory",
    "gold_memory",
    "retrieved_memory",
    "unlabeled_memory",
    "witnessed_state_labeled_memory",
    "distractors",
    "poison",
    "governed_admission",
)
OFFICIAL_STALE_SHA256 = "5f3ec375179e20e2e94469e018189188f34e2e7e5f21cbecbd99fcfa648c1876"
OFFICIAL_STALE_REPOSITORY_COMMIT = "ea7d391103a151927cd29d2f01d87597a782bdcb"
OFFICIAL_STALE_LICENSE = "CC-BY-4.0"
OFFICIAL_STALE_MODEL_GRADING_BLOCKER = "official STALE model grading requires generated responses and the upstream model judge; this no-LLM adapter produced no model responses and made no judge calls"
OFFICIAL_STALE_MODEL_PROVIDER = "OpenRouter"
OFFICIAL_STALE_TARGET_MODEL = "openai/gpt-4o-mini"
OFFICIAL_STALE_JUDGE_MODEL = "openai/gpt-4o-mini"
OFFICIAL_STALE_MODEL_SMOKE_CASES = 5
OFFICIAL_STALE_MODEL_MAX_SPEND_USD = 10.0
OFFICIAL_STALE_MODEL_CALL_TIMEOUT_SECONDS = 180
OFFICIAL_STALE_MODEL_MAX_RETRIES = 3
OFFICIAL_STALE_EVALUATOR_FILES = (
    "STALE/Evaluation/run_target_model.py",
    "STALE/Evaluation/full_eval_performance.py",
    "STALE/Evaluation/judge_prompts.py",
)
OFFICIAL_STALE_METRICS = (
    "current_state_selection",
    "stale_suppression",
    "conflict_preservation",
    "false_premise_resistance_proxy",
    "action_safe_evidence_packet",
    "historical_reconstruction",
    "abstain_request_evidence_correctness",
    "latency_ms",
    "failures",
)
OFFICIAL_STALE_RANKING_METRICS = (
    "recall_at_k",
    "mrr",
    "ndcg",
    "stale_at_rank",
    "current_vs_stale_ordering",
    "safe_evidence_rate",
    "latency_ms",
    "failures",
)
OFFICIAL_STALE_RANKING_K = (1, 3, 5)
OFFICIAL_STALE_RANKING_CANDIDATE_KINDS = (
    "current_target",
    "stale_predecessor",
    "lexical_distractor",
    "semantic_distractor",
    "unrelated_high_similarity",
    "conflict_candidate",
)
OFFICIAL_STALE_CELLS = (
    "semantic_memory",
    "mutable_latest",
    "append_only",
    "no_memory",
    "full_context_oracle",
)
OFFICIAL_SLEEPER_REPOSITORY_COMMIT = "1eb8b7e33b505299155baf3be776545b1620f022"
OFFICIAL_SLEEPER_LICENSE_CAVEAT = "Code, prompts, adversarial goals, and benchmark annotations are released by Sleeper; bundled evaluation data may derive from third-party corpora whose licenses or terms continue to govern source-derived portions."
OFFICIAL_SLEEPER_CELLS = (
    "ungoverned_append_only",
    "mutable_latest",
    "governed_semantic_memory",
    "no_memory",
)
OFFICIAL_SLEEPER_METRICS = (
    "write_admission_outcome",
    "poison_memory_retrieval_containment",
    "assertion_authority_containment",
    "action_authority_containment",
    "benign_save_retention",
    "no_write_outcome_taxonomy",
    "latency_ms",
    "failures",
)
OFFICIAL_SLEEPER_NOT_TESTED_METRICS = (
    "response_quality",
    "attack_success",
    "semantic_score",
    "model_graded",
)
OFFICIAL_SLEEPER_MODEL_GRADING_BLOCKER = "official Sleeper response-quality, attack-success, semantic-score, and model-graded metrics require subject/manager/judge provider inference; this deterministic adapter made no provider or judge calls"
OFFICIAL_SLEEPER_DATASETS = (
    ("behavior", "datasets/released/behaviour_eval_in_with_true_optimized_goals.json", "datasets/released/generated/behaviour_true_optimized_with_memories.json", 250, "poison"),
    ("agent_action", "datasets/released/agent_eval_in_with_true_optimized_goals.json", "datasets/released/generated/agent_true_optimized_with_memories.json", 100, "poison"),
    ("non_english", "datasets/released/non_english_ood_eval_with_true_optimized_goals_and_queries_mixed_seed_memories.json", "datasets/released/generated/non_english_true_optimized_with_memories.json", 100, "poison"),
    ("benign_save", "datasets/released/benign_save/merged_eval_in_benign_save_70_true_opt.json", "datasets/released/benign_save/merged_eval_in_benign_save_70_true_opt.json", 70, "benign"),
)


def sha256_path(path: Path) -> str:
    """Hash a local artifact without treating its name as provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def sha256_json(value: Any) -> str:
    """Canonical JSON digest for an embedded, local adapter fixture."""
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_official_stale_dataset(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the pinned upstream STALE file without copying it into tracked source."""
    actual_hash = sha256_path(path)
    expected_hash = f"sha256:{OFFICIAL_STALE_SHA256}"
    if actual_hash != expected_hash:
        raise ValueError(f"official STALE SHA-256 mismatch: expected {expected_hash}, got {actual_hash}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 400:
        raise ValueError("official STALE dataset must contain exactly 400 rows")
    required = {"uid", "M_old", "M_new", "explanation", "probing_queries", "relevant_session_index", "timestamps", "haystack_session", "type"}
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"official STALE row {index} has an unexpected contract")
        sessions = row["haystack_session"]
        timestamps = row["timestamps"]
        relevant = row["relevant_session_index"]
        probes = row["probing_queries"]
        if not isinstance(sessions, list) or len(sessions) != 50:
            raise ValueError(f"official STALE row {index} must contain 50 ordered sessions")
        if not isinstance(timestamps, list) or len(timestamps) != 50:
            raise ValueError(f"official STALE row {index} must contain 50 timestamps")
        if not isinstance(relevant, list) or len(relevant) != 2 or not all(isinstance(item, int) and 0 <= item < 50 for item in relevant):
            raise ValueError(f"official STALE row {index} must contain two valid relevant session indices")
        if relevant[0] >= relevant[1]:
            raise ValueError(f"official STALE row {index} relevant session indices must be ordered old then new")
        if not isinstance(probes, dict) or set(probes) != {"dim1_query", "dim2_query", "dim3_query"}:
            raise ValueError(f"official STALE row {index} must contain all three probes")
        if row["type"] not in {"T1", "T2"}:
            raise ValueError(f"official STALE row {index} has an unsupported type")
    return value, {
        "path": str(path),
        "sha256": actual_hash,
        "repository_commit": OFFICIAL_STALE_REPOSITORY_COMMIT,
        "license": OFFICIAL_STALE_LICENSE,
        "rows": len(value),
    }


def validate_official_stale_retrieval_receipt(
    dataset_row: dict[str, Any], receipt: dict[str, Any], index: int
) -> None:
    """Require an actual current-state witnessed receipt before model use."""
    if receipt.get("case_index") != index or receipt.get("case_id") != dataset_row.get("uid"):
        raise ValueError(f"official STALE retrieval receipt {index} is not linked to the dataset row")
    semantic = (receipt.get("cells") or {}).get("semantic_memory")
    if not isinstance(semantic, dict) or semantic.get("status") != "measured":
        raise ValueError(f"official STALE retrieval receipt {index} semantic_memory status is not measured")
    transition = semantic.get("transition_receipt")
    current_id = transition.get("new_result_id") if isinstance(transition, dict) else None
    if not isinstance(current_id, str) or not current_id.startswith("fact:"):
        raise ValueError(f"official STALE retrieval receipt {index} has no current fact transition receipt")
    evidence = semantic.get("evidence_packet")
    witnesses = semantic.get("witness_receipts")
    retrieved_all = True
    for probe in ("dim1_query", "dim2_query", "dim3_query"):
        probe_evidence = evidence.get(probe) if isinstance(evidence, dict) else None
        if probe_evidence not in ([], [current_id]):
            raise ValueError(f"official STALE retrieval receipt {index} {probe} does not link the current fact or an explicit empty retrieval")
        retrieved_all = retrieved_all and probe_evidence == [current_id]
        if not isinstance(witnesses, dict) or not isinstance(witnesses.get(probe), str) or not witnesses[probe]:
            raise ValueError(f"official STALE retrieval receipt {index} {probe} has no witness receipt")
    failures = (semantic.get("metrics") or {}).get("failures")
    if failures != []:
        raise ValueError(f"official STALE retrieval receipt {index} contains retrieval failures")
    expected_state = "M_new" if retrieved_all else None
    expected_disposition = "respond" if retrieved_all else "request_evidence"
    if semantic.get("selected_state") != expected_state or semantic.get("disposition") != expected_disposition:
        raise ValueError(f"official STALE retrieval receipt {index} state disposition disagrees with its evidence")
    if receipt.get("M_new") != dataset_row.get("M_new") or receipt.get("probes") != dataset_row.get("probing_queries"):
        raise ValueError(f"official STALE retrieval receipt {index} content does not match the pinned dataset")


def load_official_stale_retrieval_receipts(
    path: Path, dataset_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load the existing 400-case JSONL sidecar; never synthesize absent retrievals."""
    receipts = _load_jsonl(path)
    if len(dataset_rows) != 400 or len(receipts) != 400:
        raise ValueError("official STALE model grading requires exactly 400 dataset and retrieval receipt rows")
    for index, (dataset_row, receipt) in enumerate(zip(dataset_rows, receipts)):
        validate_official_stale_retrieval_receipt(dataset_row, receipt, index)
    return receipts, {"path": str(path), "sha256": sha256_path(path), "rows": len(receipts)}


def build_official_stale_model_input(
    dataset_row: dict[str, Any], retrieval_receipt: dict[str, Any]
) -> dict[str, Any]:
    """Adapt witnessed current memory to the pinned target script's history contract."""
    new_index = dataset_row["relevant_session_index"][1]
    current_id = retrieval_receipt["cells"]["semantic_memory"]["transition_receipt"]["new_result_id"]
    evidence = retrieval_receipt["cells"]["semantic_memory"]["evidence_packet"]
    histories = {
        probe: ([[{"role": "user", "content": retrieval_receipt["M_new"]}]] if evidence[probe] == [current_id] else [])
        for probe in ("dim1_query", "dim2_query", "dim3_query")
    }
    return {
        **dataset_row,
        "case_index": retrieval_receipt["case_index"],
        "haystack_session": [[{"role": "user", "content": retrieval_receipt["M_new"]}]],
        "timestamps": [dataset_row["timestamps"][new_index]],
        "relevant_session_index": [0, 0],
        "retrieved_haystack_by_probe": histories,
        "retrieval_witness_receipts": dict(retrieval_receipt["cells"]["semantic_memory"]["witness_receipts"]),
    }


def evaluate_official_stale_smoke_gate(
    *, smoke_cases: int, total_cases: int, returned_cost_usd: float | None,
    estimated_cost_usd: float | None, max_spend_usd: float,
) -> dict[str, Any]:
    """Project the observed five-case spend before authorizing the full run."""
    basis_name = "returned_cost_usd" if returned_cost_usd is not None else "estimated_cost_usd"
    basis = returned_cost_usd if returned_cost_usd is not None else estimated_cost_usd
    projected = round(basis * total_cases / smoke_cases, 8) if basis is not None and smoke_cases else None
    return {
        "predeclared_max_estimated_spend_usd": max_spend_usd,
        "smoke_cases": smoke_cases,
        "projection_basis": basis_name,
        "smoke_cost_usd": basis,
        "projected_full_run_usd": projected,
        "gate_passed": projected is not None and projected <= max_spend_usd,
    }


def _usage_totals(calls: list[dict[str, Any]]) -> dict[str, int]:
    return {
        key: sum(int((call.get("usage") or {}).get(key, 0) or 0) for call in calls)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def aggregate_official_stale_model_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate provider facts conservatively; absent judge results remain absent."""
    target_calls = [call for case in cases for call in (case.get("target") or {}).get("calls", [])]
    judge_calls = [case.get("judge") or {} for case in cases]
    all_calls = target_calls + judge_calls
    returned_costs = [
        float((call.get("usage") or {})["cost"])
        for call in all_calls
        if isinstance((call.get("usage") or {}).get("cost"), (int, float))
    ]
    dimensions: dict[str, Any] = {}
    total_correct = total_judged = 0
    for dim in ("dim1", "dim2", "dim3"):
        values = [
            case["judge"]["evaluation"][f"{dim}_eval"]["pass"]
            for case in cases
            if isinstance((case.get("judge") or {}).get("evaluation"), dict)
            and isinstance(case["judge"]["evaluation"].get(f"{dim}_eval"), dict)
            and isinstance(case["judge"]["evaluation"][f"{dim}_eval"].get("pass"), bool)
        ]
        correct = sum(values)
        total_correct += correct
        total_judged += len(values)
        dimensions[dim] = {"correct": correct, "total": len(values), "accuracy": round(correct / len(values), 8) if values else None}
    retries = sum(max(0, int(call.get("attempts", 0) or 0) - 1) for call in all_calls)
    failures = sum(call.get("status") != "succeeded" for call in all_calls)
    return {
        "execution": {
            "calls": {"target": len(target_calls), "judge": len(judge_calls), "total": len(all_calls)},
            "attempts": sum(int(call.get("attempts", 0) or 0) for call in all_calls),
            "retries": retries,
            "failures": failures,
        },
        "tokens": {
            "target": _usage_totals(target_calls),
            "judge": _usage_totals(judge_calls),
            "overall": _usage_totals(all_calls),
        },
        "cost": {
            "returned_usd": round(sum(returned_costs), 8) if returned_costs else None,
            "returned_cost_calls": len(returned_costs),
            "currency": "USD",
        },
        "accuracy": {
            **dimensions,
            "overall": round(total_correct / total_judged, 8) if total_judged else None,
            "correct": total_correct,
            "total": total_judged,
        },
    }


def _load_official_stale_evaluator(root: Path) -> tuple[Any, str, dict[str, str]]:
    """Load prompt helpers from the exact pinned upstream evaluator checkout."""
    result = subprocess.run(("git", "-C", str(root), "rev-parse", "HEAD"), text=True, capture_output=True, timeout=5)
    commit = result.stdout.strip() if result.returncode == 0 else ""
    if commit != OFFICIAL_STALE_REPOSITORY_COMMIT:
        raise ValueError(f"official STALE evaluator commit mismatch: expected {OFFICIAL_STALE_REPOSITORY_COMMIT}, got {commit or 'unknown'}")
    hashes: dict[str, str] = {}
    for relative in OFFICIAL_STALE_EVALUATOR_FILES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"official STALE evaluator file is absent: {path}")
        hashes[relative] = sha256_path(path)
    target_path = root / OFFICIAL_STALE_EVALUATOR_FILES[0]
    spec = importlib.util.spec_from_file_location("stale_official_run_target_model", target_path)
    if spec is None or spec.loader is None:
        raise ValueError("official STALE target evaluator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    judge_scope: dict[str, Any] = {}
    exec((root / "STALE/Evaluation/judge_prompts.py").read_text(encoding="utf-8"), judge_scope)
    return module, str(judge_scope["SYSTEM_PROMPT_ALL_IN_ONE_JUDGE"]), hashes


def _official_stale_provider_label() -> str:
    base_url = os.environ.get("OFFICIAL_STALE_MODEL_BASE_URL")
    return f"OpenAI-compatible:{base_url}" if base_url else OFFICIAL_STALE_MODEL_PROVIDER


def _openrouter_request(api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    base_url = os.environ.get("OFFICIAL_STALE_MODEL_BASE_URL")
    endpoint = (
        f"{base_url.rstrip('/')}/chat/completions"
        if base_url
        else "https://openrouter.ai/api/v1/chat/completions"
    )
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=OFFICIAL_STALE_MODEL_CALL_TIMEOUT_SECONDS) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("provider response was not a JSON object")
    return value


def _provider_call(api_key: str, payload: dict[str, Any], *, call_kind: str, case_index: int, dimension: str | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    errors: list[str] = []
    started = time.perf_counter()
    for attempt in range(1, OFFICIAL_STALE_MODEL_MAX_RETRIES + 1):
        try:
            raw = _openrouter_request(api_key, payload)
            choices = raw.get("choices")
            content = choices[0]["message"]["content"] if isinstance(choices, list) and choices else None
            if not isinstance(content, str):
                raise ValueError("provider response has no string assistant content")
            raw_usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
            usage = {
                "prompt_tokens": int(raw_usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(raw_usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(raw_usage.get("total_tokens", 0) or 0),
            }
            if isinstance(raw_usage.get("cost"), (int, float)):
                usage["cost"] = float(raw_usage["cost"])
            return ({
                "kind": call_kind,
                "dimension": dimension,
                "status": "succeeded",
                "attempts": attempt,
                "elapsed_seconds": round(time.perf_counter() - started, 6),
                "usage": usage,
                "returned_model": raw.get("model") if isinstance(raw.get("model"), str) else None,
                "provider": raw.get("provider") if isinstance(raw.get("provider"), str) else None,
                "response_id": raw.get("id") if isinstance(raw.get("id"), str) else None,
                "content": content,
                "errors": errors,
            }, {"case_index": case_index, "kind": call_kind, "dimension": dimension, "response": raw})
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            if attempt < OFFICIAL_STALE_MODEL_MAX_RETRIES:
                time.sleep(2 ** (attempt - 1))
    return ({
        "kind": call_kind,
        "dimension": dimension,
        "status": "failed",
        "attempts": OFFICIAL_STALE_MODEL_MAX_RETRIES,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "usage": {},
        "returned_model": None,
        "provider": None,
        "response_id": None,
        "content": "ERROR: Failed after multiple retries.",
        "errors": errors,
    }, None)


def _parse_official_stale_judge(content: str) -> dict[str, Any]:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.S)
    value = json.loads(match.group(1) if match else content)
    if not isinstance(value, dict) or set(value) != {"dim1_eval", "dim2_eval", "dim3_eval"}:
        raise ValueError("official STALE judge output has an unexpected object contract")
    for dim in ("dim1", "dim2", "dim3"):
        item = value[f"{dim}_eval"]
        if not isinstance(item, dict) or not isinstance(item.get("pass"), bool) or not isinstance(item.get("reasoning"), str):
            raise ValueError(f"official STALE judge output has an invalid {dim} result")
    return value


def _official_stale_judge_user_prompt(row: dict[str, Any], responses: dict[str, str]) -> str:
    probes = row["probing_queries"]
    return f"""
[Ground Truth Context]
- M_old: \"{row['M_old']}\"
- M_new: \"{row['M_new']}\"
- Hidden Logic: {row['explanation']}

--------------------------------------------------
[Dimension 1: Explicit Probing]
Question 1: {probes['dim1_query']}
Target Model Response 1: {responses['dim1_response']}

--------------------------------------------------
[Dimension 2: Adversarial Robustness]
Question 2: {probes['dim2_query']}
Target Model Response 2: {responses['dim2_response']}

--------------------------------------------------
[Dimension 3: Implicit Task]
Question 3: {probes['dim3_query']}
Target Model Response 3: {responses['dim3_response']}
"""


def _run_official_stale_model_batch(
    inputs: list[dict[str, Any]], *, target_helper: Any, judge_prompt: str,
    api_key: str, target_model: str, judge_model: str, concurrency: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_responses: list[dict[str, Any]] = []
    target_jobs: list[tuple[int, str, dict[str, Any]]] = []
    for item in inputs:
        for dim_key in ("dim1_query", "dim2_query", "dim3_query"):
            sessions = item["retrieved_haystack_by_probe"][dim_key]
            timestamps = item["timestamps"] if sessions else []
            history = target_helper.format_haystack(sessions, timestamps)
            system_prompt, user_prompt = target_helper.build_prompts(history, item["probing_queries"][dim_key], dim_key)
            payload = {"model": target_model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
            target_jobs.append((item["case_index"], dim_key, payload))
    target_by_case: dict[int, dict[str, dict[str, Any]]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_provider_call, api_key, payload, call_kind="target", case_index=index, dimension=dim): (index, dim)
            for index, dim, payload in target_jobs
        }
        for future in concurrent.futures.as_completed(futures):
            index, dim = futures[future]
            call, raw = future.result()
            target_by_case.setdefault(index, {})[dim] = call
            if raw is not None:
                raw_responses.append(raw)
    cases: list[dict[str, Any]] = []
    judge_jobs: list[tuple[dict[str, Any], dict[str, str], dict[str, Any]]] = []
    for item in inputs:
        calls = [target_by_case[item["case_index"]][dim] for dim in ("dim1_query", "dim2_query", "dim3_query")]
        responses = {f"dim{number}_response": calls[number - 1]["content"] for number in (1, 2, 3)}
        payload = {
            "model": judge_model,
            "messages": [{"role": "system", "content": judge_prompt}, {"role": "user", "content": _official_stale_judge_user_prompt(item, responses)}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        case = {
            "case_index": item["case_index"], "case_id": item["uid"], "case_type": item["type"],
            "split": "calibration" if item["case_index"] < 100 else "heldout",
            "retrieval_witness_receipts": item["retrieval_witness_receipts"],
            "target": {"responses": responses, "calls": calls},
        }
        cases.append(case)
        judge_jobs.append((case, responses, payload))
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_provider_call, api_key, payload, call_kind="judge", case_index=case["case_index"]): case
            for case, _, payload in judge_jobs
        }
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            call, raw = future.result()
            evaluation = None
            if call["status"] == "succeeded":
                try:
                    evaluation = _parse_official_stale_judge(call["content"])
                except (ValueError, json.JSONDecodeError) as exc:
                    call["status"] = "failed"
                    call["errors"].append(f"parser: {type(exc).__name__}: {exc}")
            case["judge"] = {**call, "evaluation": evaluation}
            if raw is not None:
                raw_responses.append(raw)
    cases.sort(key=lambda item: item["case_index"])
    raw_responses.sort(key=lambda item: (item["case_index"], item["kind"], item.get("dimension") or ""))
    return cases, raw_responses


def _openrouter_model_pricing(api_key: str, model: str) -> dict[str, float] | None:
    request = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
        match = next(item for item in value.get("data", []) if item.get("id") == model)
        pricing = match.get("pricing") or {}
        return {"prompt": float(pricing["prompt"]), "completion": float(pricing["completion"])}
    except (OSError, ValueError, KeyError, StopIteration, json.JSONDecodeError):
        return None


def _estimated_model_cost(aggregate: dict[str, Any], pricing: dict[str, float] | None) -> float | None:
    if pricing is None:
        return None
    tokens = aggregate["tokens"]["overall"]
    return round(tokens["prompt_tokens"] * pricing["prompt"] + tokens["completion_tokens"] * pricing["completion"], 8)


def build_official_stale_model_smoke_blocker(
    *, cases: list[dict[str, Any]], evaluator_root: Path, evaluator_hashes: dict[str, str],
    target_model: str, judge_model: str, gate: dict[str, Any], pricing: dict[str, float] | None,
    smoke_raw_path: Path, smoke_cases_path: Path, dataset_source: dict[str, Any], retrieval_source: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    aggregate = aggregate_official_stale_model_cases(cases)
    return {
        "status": "not_tested",
        "reason": reason,
        "evaluator": {"repository_root": str(evaluator_root), "repository_commit": OFFICIAL_STALE_REPOSITORY_COMMIT, "files": evaluator_hashes},
        "provider": _official_stale_provider_label(),
        "models": {"target_requested": target_model, "judge_requested": judge_model, "target_returned": [], "judge_returned": []},
        "budget": gate,
        "execution": {**aggregate["execution"], "cases": len(cases), "full_run_aborted": True, "active_services_modified": False, "network_dataset_downloads": 0},
        "tokens": aggregate["tokens"],
        "cost": {**aggregate["cost"], "estimated_usd": _estimated_model_cost(aggregate, pricing), "pricing_per_token": pricing},
        "accuracy": aggregate["accuracy"],
        "artifacts": {
            "dataset": dataset_source, "retrieval_receipts": retrieval_source,
            "smoke_raw": {"path": str(smoke_raw_path), "rows": sum(call.get("status") == "succeeded" for case in cases for call in case["target"]["calls"] + [case["judge"]]), "sha256": sha256_path(smoke_raw_path)},
            "smoke_cases": {"path": str(smoke_cases_path), "rows": len(cases), "sha256": sha256_path(smoke_cases_path)},
        },
        "claim_boundary": "No official model-graded score is reported because the five-case target+judge calibration smoke did not complete. The full 400-case run was not started. The requested openai/gpt-4o-mini target and judge via OpenRouter are not paper models, and semantic-memory retrieval-receipt context is not the paper full-haystack target context.",
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return sha256_path(path)


def run_official_stale_model_grading(
    dataset_path: Path, retrieval_receipts_path: Path, evaluator_root: Path, output_dir: Path,
    *, concurrency: int = 10, max_spend_usd: float = OFFICIAL_STALE_MODEL_MAX_SPEND_USD,
    target_model: str = OFFICIAL_STALE_TARGET_MODEL, judge_model: str = OFFICIAL_STALE_JUDGE_MODEL,
    api_key: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run the pinned STALE target and judge prompts over witnessed retrieval contexts."""
    if max_spend_usd > OFFICIAL_STALE_MODEL_MAX_SPEND_USD or max_spend_usd <= 0:
        raise ValueError("official STALE model grading max spend must be positive and no greater than $10")
    if concurrency < 1 or concurrency > 20:
        raise ValueError("official STALE model grading concurrency must be between 1 and 20")
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is required for official STALE model grading")
    rows, dataset_source = load_official_stale_dataset(dataset_path)
    receipts, retrieval_source = load_official_stale_retrieval_receipts(retrieval_receipts_path, rows)
    target_helper, judge_prompt, evaluator_hashes = _load_official_stale_evaluator(evaluator_root)
    inputs = [build_official_stale_model_input(row, receipt) for row, receipt in zip(rows, receipts)]
    pricing = (
        _openrouter_model_pricing(key, target_model)
        if target_model == judge_model and not os.environ.get("OFFICIAL_STALE_MODEL_BASE_URL")
        else None
    )
    smoke_cases, smoke_raw = _run_official_stale_model_batch(
        inputs[:OFFICIAL_STALE_MODEL_SMOKE_CASES], target_helper=target_helper, judge_prompt=judge_prompt,
        api_key=key, target_model=target_model, judge_model=judge_model, concurrency=concurrency,
    )
    smoke_aggregate = aggregate_official_stale_model_cases(smoke_cases)
    smoke_complete = (
        smoke_aggregate["execution"]["calls"] == {"target": 15, "judge": 5, "total": 20}
        and smoke_aggregate["execution"]["failures"] == 0
        and smoke_aggregate["accuracy"]["total"] == 15
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    smoke_raw_path = output_dir / "raw-smoke-provider-responses.jsonl"
    smoke_cases_path = output_dir / "smoke-model-cases.jsonl"
    _write_jsonl(smoke_raw_path, smoke_raw)
    _write_jsonl(smoke_cases_path, smoke_cases)
    smoke_returned = smoke_aggregate["cost"]["returned_usd"] if smoke_aggregate["cost"]["returned_cost_calls"] == 20 else None
    smoke_estimated = _estimated_model_cost(smoke_aggregate, pricing)
    gate = evaluate_official_stale_smoke_gate(
        smoke_cases=OFFICIAL_STALE_MODEL_SMOKE_CASES, total_cases=400,
        returned_cost_usd=smoke_returned, estimated_cost_usd=smoke_estimated, max_spend_usd=max_spend_usd,
    )
    smoke_receipt_path = output_dir / "smoke-receipt.json"
    smoke_receipt = {
        "schema": SCHEMA,
        "kind": "official_stale_model_grading_smoke",
        "status": "passed" if smoke_complete and gate["gate_passed"] else "failed",
        "cases": OFFICIAL_STALE_MODEL_SMOKE_CASES,
        "parser_validated": smoke_complete,
        "receipt_validated": smoke_complete,
        "provider": _official_stale_provider_label(),
        "models": {"target": target_model, "judge": judge_model},
        "budget": gate,
        "execution": smoke_aggregate["execution"],
        "tokens": smoke_aggregate["tokens"],
        "cost": {**smoke_aggregate["cost"], "estimated_usd": smoke_estimated, "pricing_per_token": pricing},
        "accuracy": smoke_aggregate["accuracy"],
        "evaluator": {"repository_commit": OFFICIAL_STALE_REPOSITORY_COMMIT, "files": evaluator_hashes},
        "artifacts": {
            "raw": {"path": str(smoke_raw_path), "sha256": sha256_path(smoke_raw_path)},
            "cases": {"path": str(smoke_cases_path), "sha256": sha256_path(smoke_cases_path)},
        },
    }
    smoke_receipt_path.write_text(json.dumps(smoke_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not smoke_complete:
        reason = "official STALE five-case target+judge smoke failed provider/parser/receipt validation; full run aborted and no missing judge score was synthesized"
        return build_official_stale_model_smoke_blocker(
            cases=smoke_cases, evaluator_root=evaluator_root, evaluator_hashes=evaluator_hashes,
            target_model=target_model, judge_model=judge_model, gate=gate, pricing=pricing,
            smoke_raw_path=smoke_raw_path, smoke_cases_path=smoke_cases_path,
            dataset_source=dataset_source, retrieval_source=retrieval_source, reason=reason,
        ), smoke_cases
    if not gate["gate_passed"]:
        raise RuntimeError(f"official STALE full run aborted by $10 gate; projected ${gate['projected_full_run_usd']}")
    remaining_cases, remaining_raw = _run_official_stale_model_batch(
        inputs[OFFICIAL_STALE_MODEL_SMOKE_CASES:], target_helper=target_helper, judge_prompt=judge_prompt,
        api_key=key, target_model=target_model, judge_model=judge_model, concurrency=concurrency,
    )
    cases = smoke_cases + remaining_cases
    raw = smoke_raw + remaining_raw
    aggregate = aggregate_official_stale_model_cases(cases)
    estimated_cost = _estimated_model_cost(aggregate, pricing)
    if estimated_cost is not None and estimated_cost > max_spend_usd:
        raise RuntimeError(f"official STALE estimated spend exceeded the predeclared maximum: ${estimated_cost}")
    raw_path = output_dir / "raw-provider-responses.jsonl"
    cases_path = output_dir / "model-graded-per-case.jsonl"
    raw_hash = _write_jsonl(raw_path, raw)
    cases_hash = _write_jsonl(cases_path, cases)
    target_returned = sorted({call["returned_model"] for case in cases for call in case["target"]["calls"] if call["returned_model"]})
    judge_returned = sorted({case["judge"]["returned_model"] for case in cases if case["judge"]["returned_model"]})
    receipt = {
        "status": "measured",
        "evaluator": {"repository_root": str(evaluator_root), "repository_commit": OFFICIAL_STALE_REPOSITORY_COMMIT, "files": evaluator_hashes},
        "provider": _official_stale_provider_label(),
        "models": {"target_requested": target_model, "judge_requested": judge_model, "target_returned": target_returned, "judge_returned": judge_returned},
        "budget": gate,
        "execution": {**aggregate["execution"], "cases": len(cases), "concurrency": concurrency, "active_services_modified": False, "network_dataset_downloads": 0},
        "tokens": aggregate["tokens"],
        "cost": {**aggregate["cost"], "estimated_usd": estimated_cost, "pricing_per_token": pricing, "estimate_method": "OpenRouter model metadata times returned tokens" if pricing else None},
        "accuracy": aggregate["accuracy"],
        "artifacts": {
            "dataset": dataset_source, "retrieval_receipts": retrieval_source,
            "raw_provider_responses": {"path": str(raw_path), "rows": len(raw), "sha256": raw_hash},
            "per_case": {"path": str(cases_path), "rows": len(cases), "sha256": cases_hash},
            "smoke_raw": {"path": str(smoke_raw_path), "rows": len(smoke_raw), "sha256": sha256_path(smoke_raw_path)},
            "smoke_cases": {"path": str(smoke_cases_path), "rows": len(smoke_cases), "sha256": sha256_path(smoke_cases_path)},
            "smoke_receipt": {"path": str(smoke_receipt_path), "sha256": sha256_path(smoke_receipt_path)},
        },
        "claim_boundary": "Uses the pinned official STALE target prompt construction and all-in-one judge rubric/parser with the official dataset, but openai/gpt-4o-mini via OpenRouter is not a paper model and per-probe semantic-memory retrieval-receipt context replaces the paper full-haystack target context; this is an official-evaluator system-configuration result, not a paper-model reproduction.",
    }
    return receipt, cases


def load_official_sleeper_datasets(root: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Load pinned Sleeper release splits without copying their data into this repo."""
    if not (root / ".git").exists():
        raise ValueError(f"official Sleeper root is not a git checkout: {root}")
    result = subprocess.run(("git", "-C", str(root), "rev-parse", "HEAD"), text=True, capture_output=True, timeout=5)
    actual_commit = result.stdout.strip() if result.returncode == 0 else "unknown"
    if actual_commit != OFFICIAL_SLEEPER_REPOSITORY_COMMIT:
        raise ValueError(f"official Sleeper commit mismatch: expected {OFFICIAL_SLEEPER_REPOSITORY_COMMIT}, got {actual_commit}")
    datasets: list[dict[str, Any]] = []
    slices: dict[str, list[dict[str, Any]]] = {}
    for slice_id, source_relative, split_relative, expected_rows, kind in OFFICIAL_SLEEPER_DATASETS:
        source_path = root / source_relative
        split_path = root / split_relative
        if not source_path.is_file() or not split_path.is_file():
            raise ValueError(f"official Sleeper released dataset/split is absent for {slice_id}")
        rows = json.loads(split_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or len(rows) != expected_rows:
            raise ValueError(f"official Sleeper {slice_id} split must contain exactly {expected_rows} rows")
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or not {"document", "goal", "query", "preexisting_memories"} <= set(row):
                raise ValueError(f"official Sleeper {slice_id} row {index} has an unexpected contract")
        slices[slice_id] = rows
        datasets.append({
            "id": slice_id,
            "kind": kind,
            "source_path": str(source_path),
            "source_sha256": sha256_path(source_path),
            "split_path": str(split_path),
            "split_sha256": sha256_path(split_path),
            "rows": len(rows),
        })
    return {
        "root": str(root),
        "repository_commit": actual_commit,
        "license_caveat": OFFICIAL_SLEEPER_LICENSE_CAVEAT,
        "datasets": datasets,
    }, slices


def _official_sleeper_case_id(slice_id: str, row: dict[str, Any], index: int) -> str:
    document = row.get("document") if isinstance(row.get("document"), dict) else {}
    goal = row.get("goal") if isinstance(row.get("goal"), dict) else {}
    return f"{slice_id}:{document.get('doc_id', index)}:{goal.get('goal_id', index)}"


def project_official_sleeper_row(slice_id: str, kind: str, row: dict[str, Any], index: int) -> dict[str, Any]:
    """Keep official row linkage and content digests, never copied source text."""
    document = row["document"] if isinstance(row["document"], dict) else {}
    goal = row["goal"] if isinstance(row["goal"], dict) else {}
    query = row["query"] if isinstance(row["query"], dict) else {}
    return {
        "case_id": _official_sleeper_case_id(slice_id, row, index),
        "slice": slice_id,
        "kind": kind,
        "row_index": index,
        "document_id": document.get("doc_id"),
        "goal_id": goal.get("goal_id"),
        "language": (row.get("agent_action_metadata") or {}).get("language") if isinstance(row.get("agent_action_metadata"), dict) else None,
        "row_sha256": sha256_json(row),
        "document_sha256": sha256_json(document),
        "goal_sha256": sha256_json(goal),
        "query_sha256": sha256_json(query),
        "state_framing": {
            "origin": "external_content" if kind == "poison" else "user_requested_benign_save",
            "candidate_representation": "row-content digests only; no subject or manager model inferred a memory from the source document",
            "state_view": "Current",
        },
    }


def project_official_stale_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    """Project a 50-session row into a compact, ordered, replayable event stream."""
    session_digests = [sha256_json(session) for session in row["haystack_session"]]
    old_index, new_index = row["relevant_session_index"]
    return {
        "case_index": index,
        "case_id": row["uid"],
        "case_type": row["type"],
        "split": "calibration" if index < 100 else "heldout",
        "session_count": 50,
        "stream_equivalence": "all 50 ordered sessions are represented by canonical JSON SHA-256 digests; material state events retain source index, timestamp, memory text, explanation, and probes",
        "ordered_session_digests": session_digests,
        "relevant_session_index": list(row["relevant_session_index"]),
        "timestamps": list(row["timestamps"]),
        "M_old": row["M_old"],
        "M_new": row["M_new"],
        "explanation": row["explanation"],
        "probes": dict(row["probing_queries"]),
        "material_events": [
            {"kind": "M_old", "session_index": old_index, "timestamp": row["timestamps"][old_index], "memory": row["M_old"]},
            {"kind": "M_new", "session_index": new_index, "timestamp": row["timestamps"][new_index], "memory": row["M_new"], "invalidates": "M_old", "explanation": row["explanation"]},
        ],
    }


def _ranking_candidate(case_id: str, suffix: str, kind: str, content: str) -> dict[str, str]:
    """Give every deterministic candidate a stable in-content identity marker."""
    candidate_id = f"{case_id}:{suffix}"
    return {"id": candidate_id, "kind": kind, "content": f"[ranking-candidate:{candidate_id}] {content}"}


def project_official_stale_ranking_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    """Add a deterministic six-candidate ranking set to the official STALE projection.

    The candidate set is intentionally independent from the state transition
    benchmark: all six records are ordinary retrieval candidates.  The existing
    M_old -> M_new supersession path is evaluated separately in ``cells``.
    """
    projected = project_official_stale_row(row, index)
    case_id = projected["case_id"]
    dim1 = projected["probes"]["dim1_query"]
    dim2 = projected["probes"]["dim2_query"]
    dim3 = projected["probes"]["dim3_query"]
    projected["ranking_candidates"] = [
        _ranking_candidate(case_id, "current", "current_target", projected["M_new"]),
        _ranking_candidate(case_id, "stale", "stale_predecessor", projected["M_old"]),
        _ranking_candidate(case_id, "lexical", "lexical_distractor", f"Lexical overlap only; this unrelated record repeats query wording: {dim1}"),
        _ranking_candidate(case_id, "semantic", "semantic_distractor", f"Semantically adjacent but unrelated recommendation context: {dim3}"),
        _ranking_candidate(case_id, "high_similarity", "unrelated_high_similarity", f"High-similarity unrelated candidate. It shares the new-state phrasing but is not evidence for this case: {projected['M_new']}"),
        _ranking_candidate(case_id, "conflict", "conflict_candidate", f"Conflicting, non-authoritative candidate retaining the predecessor claim: {projected['M_old']}"),
    ]
    projected["ranking_policy"] = {
        "candidate_count": len(OFFICIAL_STALE_RANKING_CANDIDATE_KINDS),
        "candidate_kinds": list(OFFICIAL_STALE_RANKING_CANDIDATE_KINDS),
        "retrieval_ranking": "all candidates are retrieved as ordinary records with stable marker identities",
        "state_integrity": "measured separately from candidate ordering",
        "tuning": "calibration rows 0-99 only; heldout rows 100-399 are never used for benchmark-specific tuning",
    }
    return projected


def _ranking_position(ordered: list[str], candidate_id: str) -> int | None:
    try:
        return ordered.index(candidate_id) + 1
    except ValueError:
        return None


def score_ranking_results(
    *,
    expected_current: str,
    expected_stale: str,
    conflict_candidate: str,
    ordered_candidate_ids: dict[str, list[str]],
    latency_ms: float,
    failures: list[str],
) -> dict[str, Any]:
    """Score ordering only; state transition correctness is deliberately absent."""
    rankings = list(ordered_candidate_ids.values())
    count = len(rankings)
    ranks = [_ranking_position(ordered, expected_current) for ordered in rankings]
    stale_ranks = [_ranking_position(ordered, expected_stale) for ordered in rankings]
    conflict_ranks = [_ranking_position(ordered, conflict_candidate) for ordered in rankings]
    recall = {
        str(k): (sum(rank is not None and rank <= k for rank in ranks) / count if count else 0.0)
        for k in OFFICIAL_STALE_RANKING_K
    }
    mrr = sum(1 / rank if rank is not None else 0.0 for rank in ranks) / count if count else 0.0
    # With one relevant target, nDCG is 1/log2(rank+1).
    import math
    ndcg = sum(1 / math.log2(rank + 1) if rank is not None else 0.0 for rank in ranks) / count if count else 0.0
    ordered_current = sum(
        current is not None and (stale is None or current < stale)
        for current, stale in zip(ranks, stale_ranks)
    ) / count if count else 0.0
    safe_evidence = sum(
        current is not None and current <= 3 and (stale is None or current < stale) and (conflict is None or current < conflict)
        for current, stale, conflict in zip(ranks, stale_ranks, conflict_ranks)
    ) / count if count else 0.0
    return {
        "recall_at_k": recall,
        "mrr": mrr,
        "ndcg": ndcg,
        "stale_at_rank": {probe: _ranking_position(ordered, expected_stale) for probe, ordered in ordered_candidate_ids.items()},
        "current_vs_stale_ordering": ordered_current,
        "safe_evidence_rate": safe_evidence,
        "latency_ms": round(latency_ms, 6),
        "failures": list(failures),
    }


def aggregate_ranking_metrics(cases: list[dict[str, Any]], cell: str = "ranking") -> dict[str, Any]:
    """Aggregate only ranking metrics and explicitly reserve state for its own cell."""
    measured = [case[cell] for case in cases if case.get(cell, {}).get("status") in {"measured", "failed"}]
    probe_total = len(measured) * 3
    metrics: dict[str, Any] = {
        "recall_at_k": {
            str(k): {
                "successes": round(sum(item["metrics"]["recall_at_k"][str(k)] * 3 for item in measured)),
                "total": probe_total,
                "rate": round(sum(item["metrics"]["recall_at_k"][str(k)] for item in measured) / len(measured), 6) if measured else None,
            }
            for k in OFFICIAL_STALE_RANKING_K
        },
        "mrr": {"mean": round(sum(item["metrics"]["mrr"] for item in measured) / len(measured), 6) if measured else None},
        "ndcg": {"mean": round(sum(item["metrics"]["ndcg"] for item in measured) / len(measured), 6) if measured else None},
        "stale_at_rank": {"per_probe": [item["metrics"]["stale_at_rank"] for item in measured], "count": probe_total},
        "current_vs_stale_ordering": {"successes": round(sum(item["metrics"]["current_vs_stale_ordering"] * 3 for item in measured)), "total": probe_total, "rate": round(sum(item["metrics"]["current_vs_stale_ordering"] for item in measured) / len(measured), 6) if measured else None},
        "safe_evidence_rate": {"successes": round(sum(item["metrics"]["safe_evidence_rate"] * 3 for item in measured)), "total": probe_total, "rate": round(sum(item["metrics"]["safe_evidence_rate"] for item in measured) / len(measured), 6) if measured else None},
        "latency_ms": {"count": len(measured), "mean": round(sum(item["metrics"]["latency_ms"] for item in measured) / len(measured), 6) if measured else None, "max": max((item["metrics"]["latency_ms"] for item in measured), default=None)},
        "failures": {"count": sum(len(item["metrics"]["failures"]) for item in measured)},
        "state_integrity": {"status": "separate"},
    }
    return {cell: {"status": "measured" if measured else "not_tested", "metrics": metrics}}


def select_competitor_stale_cases(cases: list[dict[str, Any]], *, all_rows: bool = False) -> list[dict[str, Any]]:
    """Apply the predeclared smoke/held-out selection, or its post-smoke all-row promotion."""
    if all_rows:
        return list(cases)
    by_index = {int(case["case_index"]): case for case in cases}
    missing = [index for index in COMPETITOR_STALE_SMOKE_INDICES if index not in by_index]
    if missing:
        raise ValueError(f"competitor STALE selection is missing predeclared rows: {missing}")
    return [by_index[index] for index in COMPETITOR_STALE_SMOKE_INDICES]


def _unmeasured_competitor(competitor_id: str, reason: str) -> dict[str, Any]:
    return {
        "id": competitor_id,
        "name": COMPETITOR_PINS[competitor_id]["name"],
        "status": "not_tested",
        "reason": reason,
        "upstream": dict(COMPETITOR_PINS[competitor_id]),
        "benchmarks": {
            "stale": {"status": "not_tested", "reason": reason},
            "sleeper": {
                "status": "not_supported",
                "reason": "no documented public write-admission or governance mechanism was identified; ordinary memory insertion is not scored as governance",
            },
        },
    }


def initial_competitor_records() -> dict[str, dict[str, Any]]:
    reason = "no isolated competitor interpreter or blocker receipt was supplied"
    return {competitor_id: _unmeasured_competitor(competitor_id, reason) for competitor_id in COMPETITOR_IDS}


def _baseline_stale_cells(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Deterministic controls over the same projected state events; no response model."""
    old_ref = f"{case['case_id']}:M_old"
    new_ref = f"{case['case_id']}:M_new"
    return {
        "mutable_latest": {
            "status": "measured", "evidence_packet": [new_ref], "selected_state": "M_new", "disposition": "respond",
            "metrics": {"current_state_selection": True, "stale_suppression": True, "conflict_preservation": False, "false_premise_resistance_proxy": True, "action_safe_evidence_packet": True, "historical_reconstruction": False, "abstain_request_evidence_correctness": True, "latency_ms": 0.0, "failures": []},
        },
        "append_only": {
            "status": "measured", "evidence_packet": [old_ref, new_ref], "selected_state": None, "disposition": "request_evidence",
            "metrics": {"current_state_selection": False, "stale_suppression": False, "conflict_preservation": True, "false_premise_resistance_proxy": False, "action_safe_evidence_packet": False, "historical_reconstruction": True, "abstain_request_evidence_correctness": True, "latency_ms": 0.0, "failures": []},
        },
        "no_memory": {
            "status": "measured", "evidence_packet": [], "selected_state": None, "disposition": "request_evidence",
            "metrics": {"current_state_selection": False, "stale_suppression": True, "conflict_preservation": False, "false_premise_resistance_proxy": False, "action_safe_evidence_packet": False, "historical_reconstruction": False, "abstain_request_evidence_correctness": True, "latency_ms": 0.0, "failures": []},
        },
        "full_context_oracle": {
            "status": "measured", "evidence_packet": [new_ref], "selected_state": "M_new", "disposition": "respond",
            "metrics": {"current_state_selection": True, "stale_suppression": True, "conflict_preservation": True, "false_premise_resistance_proxy": True, "action_safe_evidence_packet": True, "historical_reconstruction": True, "abstain_request_evidence_correctness": True, "latency_ms": 0.0, "failures": []},
        },
    }


def _load_memory_trust_kernel_module() -> Any:
    """Reuse the one existing MCP client rather than defining another client here."""
    path = ROOT / "shared/scripts/benchmark-memory-trust-kernel.py"
    spec = importlib.util.spec_from_file_location("benchmark_memory_trust_kernel", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load existing MCP client from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result_text(payload: dict[str, Any]) -> str:
    return "\n".join(str(row.get("content", "")) for row in payload.get("results", []) if isinstance(row, dict))


def seconds_to_next_persisted_second(now: float) -> float:
    """Delay past the next whole second for stores with second-granularity timestamps."""
    return (1.0 - (now % 1.0)) + 0.02


def _semantic_memory_stale_case(client: Any, trust_kernel: Any, case: dict[str, Any]) -> dict[str, Any]:
    """Exercise the actual MCP/core supersession and witnessed/as-of retrieval path."""
    started = time.perf_counter()
    namespace = f"bench-stale-{case['case_index']:04d}-{case['case_id']}"
    failures: list[str] = []
    old_ok, old = client.call("sm_add_fact", {"content": case["M_old"], "namespace": namespace, "memory_kind": "durable_fact", "source": "official STALE pinned dataset"})
    old_id = trust_kernel.extract_fact_id(old) if old_ok else None
    if not old_id:
        failures.append("M_old admission failed")
    historical_at = datetime.now(timezone.utc).isoformat()
    # Facts and supersession edges are persisted at one-second granularity.
    # Cross a whole persisted-time boundary so the as-of cutoff cannot share
    # the replacement's recorded second.
    time.sleep(seconds_to_next_persisted_second(time.time()))
    replacement_ok, replacement = client.call("sm_supersede_fact", {"old_fact_id": old_id, "content": case["M_new"], "namespace": namespace, "reason": case["explanation"], "source": "official STALE pinned dataset"}) if old_id else (False, {})
    if not replacement_ok:
        failures.append("M_new supersession failed")
    current_payloads: dict[str, dict[str, Any]] = {}
    for dimension, query in case["probes"].items():
        ok, payload = client.call("sm_search_witnessed", {"query": query, "namespaces": [namespace], "top_k": 5, "request_id": f"stale-{case['case_index']}-{dimension}"})
        if not ok:
            failures.append(f"{dimension} witnessed retrieval failed")
        current_payloads[dimension] = payload
    history_ok, history = client.call("sm_search_as_of", {"query": case["probes"]["dim1_query"], "namespace": namespace, "as_of_date": historical_at, "top_k": 5})
    if not history_ok:
        failures.append("historical retrieval failed")
    current_text = {key: _result_text(value) for key, value in current_payloads.items()}
    history_text = _result_text(history)
    current_selected = all(case["M_new"] in current_text[key] for key in case["probes"])
    stale_suppressed = all(case["M_old"] not in current_text[key] for key in case["probes"])
    dim2_safe = case["M_new"] in current_text["dim2_query"] and case["M_old"] not in current_text["dim2_query"]
    dim3_safe = case["M_new"] in current_text["dim3_query"] and case["M_old"] not in current_text["dim3_query"]
    historical_old_present = case["M_old"] in history_text
    historical_new_present = case["M_new"] in history_text
    historical = historical_old_present and not historical_new_present
    evidence_packet = {
        key: [str(row.get("result_id", row.get("memory_id", "unknown"))) for row in payload.get("results", []) if isinstance(row, dict)]
        for key, payload in current_payloads.items()
    }
    disposition = "respond" if current_selected and stale_suppressed else "request_evidence"
    elapsed_ms = round((time.perf_counter() - started) * 1000, 6)
    return {
        "status": "measured" if not failures else "failed",
        "evidence_packet": evidence_packet,
        "selected_state": "M_new" if current_selected else None,
        "disposition": disposition,
        "transition_receipt": replacement,
        "witness_receipts": {key: payload.get("receipt_id") for key, payload in current_payloads.items()},
        "historical_evidence": {"M_old_present": historical_old_present, "M_new_present": historical_new_present, "exact_snapshot": historical},
        "metrics": {
            "current_state_selection": current_selected,
            "stale_suppression": stale_suppressed,
            "conflict_preservation": replacement_ok and historical_old_present and current_selected,
            "false_premise_resistance_proxy": dim2_safe,
            "action_safe_evidence_packet": dim3_safe,
            "historical_reconstruction": historical,
            "abstain_request_evidence_correctness": (disposition == "respond") == (current_selected and stale_suppressed),
            "latency_ms": elapsed_ms,
            "failures": failures,
        },
    }


def _candidate_ids_from_payload(payload: dict[str, Any]) -> list[str]:
    """Recover only predeclared marker IDs from existing retrieval result content."""
    identifiers: list[str] = []
    for row in payload.get("results", []):
        if not isinstance(row, dict):
            continue
        match = re.search(r"\[ranking-candidate:([^\]]+)\]", str(row.get("content", "")))
        if match is not None:
            identifiers.append(match.group(1))
    return identifiers


def _semantic_memory_ranking_case(client: Any, case: dict[str, Any]) -> dict[str, Any]:
    """Use the existing MCP client and witnessed retrieval for candidate ordering only."""
    started = time.perf_counter()
    namespace = f"bench-stale-ranking-{case['case_index']:04d}-{case['case_id']}"
    failures: list[str] = []
    for candidate in case["ranking_candidates"]:
        admitted, _ = client.call(
            "sm_add_fact",
            {
                "content": candidate["content"],
                "namespace": namespace,
                "memory_kind": "durable_fact",
                "source": "official STALE deterministic ranking candidate",
                "idempotency_key": "stale-ranking-" + hashlib.sha256(candidate["id"].encode("utf-8")).hexdigest(),
            },
        )
        if not admitted:
            failures.append(f"candidate admission failed: {candidate['kind']}")
    ordered: dict[str, list[str]] = {}
    for probe, query in case["probes"].items():
        ok, payload = client.call(
            "sm_search_witnessed",
            {"query": query, "namespaces": [namespace], "top_k": len(case["ranking_candidates"]), "request_id": f"stale-ranking-{case['case_index']}-{probe}"},
        )
        if not ok:
            failures.append(f"{probe} witnessed retrieval failed")
        ordered[probe] = _candidate_ids_from_payload(payload)
    candidate_ids = {candidate["kind"]: candidate["id"] for candidate in case["ranking_candidates"]}
    metrics = score_ranking_results(
        expected_current=candidate_ids["current_target"],
        expected_stale=candidate_ids["stale_predecessor"],
        conflict_candidate=candidate_ids["conflict_candidate"],
        ordered_candidate_ids=ordered,
        latency_ms=(time.perf_counter() - started) * 1000,
        failures=failures,
    )
    return {
        "status": "measured" if not failures else "failed",
        "ordered_candidate_ids": ordered,
        "candidate_taxonomy": list(OFFICIAL_STALE_RANKING_CANDIDATE_KINDS),
        "metrics": metrics,
        "claim_boundary": "candidate ordering only; current-state integrity is measured in the separate semantic_memory cell",
    }


def _aggregate_stale_metrics(cases: list[dict[str, Any]], cells: tuple[str, ...] = OFFICIAL_STALE_CELLS) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    for cell in cells:
        measured = [case["cells"][cell] for case in cases if case["cells"][cell]["status"] in {"measured", "failed"}]
        cell_metrics: dict[str, Any] = {}
        for metric in OFFICIAL_STALE_METRICS:
            if metric == "latency_ms":
                values = [float(item["metrics"][metric]) for item in measured]
                cell_metrics[metric] = {"count": len(values), "mean": round(sum(values) / len(values), 6) if values else None, "max": max(values) if values else None}
            elif metric == "failures":
                failures = [failure for item in measured for failure in item["metrics"][metric]]
                cell_metrics[metric] = {"count": len(failures)}
            else:
                successes = sum(bool(item["metrics"][metric]) for item in measured)
                cell_metrics[metric] = {"successes": successes, "total": len(measured), "rate": round(successes / len(measured), 6) if measured else None}
        aggregate[cell] = {"status": "measured" if measured else "not_tested", "metrics": cell_metrics}
    return aggregate


def _sleeper_control_cell(kind: str, cell: str) -> dict[str, Any]:
    """Predeclared non-semantic-memory controls over the same official row identity."""
    if cell == "no_memory":
        outcome, no_write = "no_write", "no_memory_configured"
        poison_contained = True if kind == "poison" else None
        benign_retained = False
    else:
        outcome, no_write = "accept", "not_applicable"
        poison_contained = False if kind == "poison" else None
        benign_retained = True if kind == "benign" else None
    return {
        "status": "measured",
        "metrics": {
            "write_admission_outcome": outcome,
            "poison_memory_retrieval_containment": poison_contained,
            "assertion_authority_containment": {"status": "not_tested", "reason": "control cell has no governed origin-authority decision"},
            "action_authority_containment": {"status": "not_tested", "reason": "control cell has no governed action-authority decision"},
            "benign_save_retention": benign_retained,
            "no_write_outcome_taxonomy": no_write,
            "latency_ms": 0.0,
            "failures": [],
        },
    }


def _sleepers_error_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _semantic_memory_sleeper_case(client: Any, case: dict[str, Any]) -> dict[str, Any]:
    """Measure only actual MCP admission and witnessed-retrieval operations."""
    started = time.perf_counter()
    marker = "sleeper-row-" + case["row_sha256"].removeprefix("sha256:")[:24]
    namespace = "bench-sleeper-" + hashlib.sha256(case["case_id"].encode("utf-8")).hexdigest()[:20]
    failures: list[str] = []
    content = f"Sleeper official deterministic row marker {marker}."
    arguments: dict[str, Any] = {
        "content": content,
        "namespace": namespace,
        "idempotency_key": "sleeper-admission-" + marker,
    }
    if case["kind"] == "poison":
        # This is an admission-boundary probe, not a claim that a model extracted
        # a particular memory from this document.  The official row remains linked
        # by immutable digests in the per-case receipt.
        arguments["memory_kind"] = "ephemeral_inference"
    else:
        arguments["memory_kind"] = "durable_fact"
        # A source reference makes the MCP append path bind an external-evidence
        # origin label whose assertion/action scopes are denied by the existing API.
        arguments["source"] = "sleeper-official-row:" + case["row_sha256"]
    admitted, admission_receipt = client.call("sm_add_fact", arguments)
    if case["kind"] == "benign" and not admitted:
        failures.append("benign-save admission failed")
    if case["kind"] == "poison" and admitted:
        failures.append("evidence-free ephemeral inference was admitted")
    retrieved, witness_receipt = client.call(
        "sm_search_witnessed",
        {"query": marker, "namespaces": [namespace], "top_k": 5, "request_id": "sleeper-recall-" + marker},
    )
    if not retrieved:
        failures.append("witnessed retrieval failed")
    witness_text = _result_text(witness_receipt)
    marker_retrieved = marker in witness_text
    if case["kind"] == "poison":
        no_write = "rejected_by_admission_gate" if not admitted and "Admission gate BLOCKED" in _sleepers_error_text(admission_receipt) else "ambiguous"
        poison_contained: bool | None = not marker_retrieved
        benign_retained: bool | None = None
    else:
        no_write = "not_applicable"
        poison_contained = None
        benign_retained = admitted and marker_retrieved
    authority_blocker = "the available MCP surface creates governed origin labels on append but exposes no purpose-specific governed assertion/action read tool; direct authority decisions were not simulated"
    return {
        "status": "measured" if not failures else "failed",
        "admission_receipt": admission_receipt,
        "witness_receipt_id": witness_receipt.get("receipt_id"),
        "origin_authority": {
            "status": "bounded_by_actual_append_contract" if case["kind"] == "benign" and admitted else "not_applicable",
            "origin": "external_evidence" if case["kind"] == "benign" and admitted else None,
            "assertion_scope": "Denied" if case["kind"] == "benign" and admitted else None,
            "action_scope": "Denied" if case["kind"] == "benign" and admitted else None,
            "multi_principal_policy": "not_tested: " + authority_blocker,
        },
        "metrics": {
            "write_admission_outcome": "accept" if admitted else "reject",
            "poison_memory_retrieval_containment": poison_contained,
            "assertion_authority_containment": {"status": "not_tested", "reason": authority_blocker},
            "action_authority_containment": {"status": "not_tested", "reason": authority_blocker},
            "benign_save_retention": benign_retained,
            "no_write_outcome_taxonomy": no_write,
            "latency_ms": round((time.perf_counter() - started) * 1000, 6),
            "failures": failures,
        },
    }


def _aggregate_sleeper_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    for cell in OFFICIAL_SLEEPER_CELLS:
        rows = [case["cells"][cell] for case in cases]
        outcomes: dict[str, int] = {}
        taxonomy: dict[str, int] = {}
        for row in rows:
            metrics = row["metrics"]
            outcome = str(metrics["write_admission_outcome"])
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            category = str(metrics["no_write_outcome_taxonomy"])
            taxonomy[category] = taxonomy.get(category, 0) + 1

        def rate(metric: str) -> dict[str, Any]:
            applicable = [item["metrics"][metric] for item in rows if item["metrics"][metric] is not None]
            return {
                "successes": sum(bool(value) for value in applicable),
                "total": len(applicable),
                "rate": round(sum(bool(value) for value in applicable) / len(applicable), 6) if applicable else None,
            }

        latencies = [float(item["metrics"]["latency_ms"]) for item in rows]
        aggregate[cell] = {
            "status": "measured" if rows else "not_tested",
            "metrics": {
                "write_admission_outcome": outcomes,
                "poison_memory_retrieval_containment": rate("poison_memory_retrieval_containment"),
                "assertion_authority_containment": {"status": "not_tested", "reason": "MCP purpose-specific governed assertion access is not exposed"},
                "action_authority_containment": {"status": "not_tested", "reason": "MCP purpose-specific governed action access is not exposed"},
                "benign_save_retention": rate("benign_save_retention"),
                "no_write_outcome_taxonomy": taxonomy,
                "latency_ms": {"count": len(latencies), "mean": round(sum(latencies) / len(latencies), 6) if latencies else None, "max": max(latencies) if latencies else None},
                "failures": {"count": sum(len(item["metrics"]["failures"]) for item in rows)},
            },
        }
    return aggregate


def run_official_sleeper_adapter(
    root: Path,
    *,
    limit_per_slice: int | None = None,
    launch_local: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run a deterministic, no-inference admission adapter over pinned Sleeper rows."""
    source, slices = load_official_sleeper_datasets(root)
    if limit_per_slice is not None and limit_per_slice < 1:
        raise ValueError("--official-sleeper-limit-per-slice must be positive")
    kinds = {item[0]: item[4] for item in OFFICIAL_SLEEPER_DATASETS}
    cases = [
        project_official_sleeper_row(slice_id, kinds[slice_id], row, index)
        for slice_id, rows in slices.items()
        for index, row in enumerate(rows[:limit_per_slice] if limit_per_slice is not None else rows)
    ]
    semantic_reason = "isolated semantic-memory MCP path was not requested; no semantic-memory behavior was simulated"
    client = None
    trust_kernel = None
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    endpoint = None
    tool_names: list[str] = []
    try:
        if launch_local:
            trust_kernel = _load_memory_trust_kernel_module()
            launcher = ROOT / "shared/scripts/run-server.sh"
            if not launcher.is_file() or not shutil.which("bash"):
                raise RuntimeError("documented local semantic-memory launcher is unavailable")
            temp_dir = tempfile.TemporaryDirectory(prefix="official-sleeper-")
            port = trust_kernel.free_port()
            endpoint = f"http://127.0.0.1:{port}"
            env = {**os.environ, "SEMANTIC_MEMORY_DIR": temp_dir.name, "SEMANTIC_MEMORY_HTTP_PORT": str(port), "SEMANTIC_MEMORY_EMBEDDER": "mock", "SEMANTIC_MEMORY_TOOL_PROFILE": "full"}
            client = trust_kernel.McpClient([str(launcher)], env)
            for _ in range(40):
                if trust_kernel.endpoint_available(endpoint):
                    break
                time.sleep(0.15)
            if not trust_kernel.endpoint_available(endpoint):
                raise RuntimeError("isolated semantic-memory HTTP/MCP surface did not become available")
            tool_names = sorted(client.tool_names())
            missing = sorted({"sm_add_fact", "sm_search_witnessed"} - set(tool_names))
            if missing:
                raise RuntimeError("isolated semantic-memory MCP surface lacks required tools: " + ", ".join(missing))
        for case in cases:
            cells = {cell: _sleeper_control_cell(case["kind"], cell) for cell in OFFICIAL_SLEEPER_CELLS if cell != "governed_semantic_memory"}
            cells["governed_semantic_memory"] = _semantic_memory_sleeper_case(client, case) if client is not None else {
                "status": "not_tested",
                "reason": semantic_reason,
                "metrics": {
                    "write_admission_outcome": "not_tested",
                    "poison_memory_retrieval_containment": None,
                    "assertion_authority_containment": {"status": "not_tested", "reason": semantic_reason},
                    "action_authority_containment": {"status": "not_tested", "reason": semantic_reason},
                    "benign_save_retention": None,
                    "no_write_outcome_taxonomy": "not_tested",
                    "latency_ms": 0.0,
                    "failures": [],
                },
            }
            case["cells"] = cells
            governed = cells["governed_semantic_memory"]
            case["no_write_outcome"] = governed["metrics"]["no_write_outcome_taxonomy"]
    except Exception as exc:
        semantic_reason = f"isolated semantic-memory MCP path unavailable: {exc}; no semantic-memory result was simulated"
        for case in cases:
            cells = {cell: _sleeper_control_cell(case["kind"], cell) for cell in OFFICIAL_SLEEPER_CELLS if cell != "governed_semantic_memory"}
            cells["governed_semantic_memory"] = {"status": "not_tested", "reason": semantic_reason, "metrics": {"write_admission_outcome": "not_tested", "poison_memory_retrieval_containment": None, "assertion_authority_containment": {"status": "not_tested", "reason": semantic_reason}, "action_authority_containment": {"status": "not_tested", "reason": semantic_reason}, "benign_save_retention": None, "no_write_outcome_taxonomy": "not_tested", "latency_ms": 0.0, "failures": []}}
            case["cells"] = cells
            case["no_write_outcome"] = "not_tested"
    finally:
        if client is not None:
            client.close()
        if temp_dir is not None:
            temp_dir.cleanup()
    measured = sum(case["cells"]["governed_semantic_memory"]["status"] in {"measured", "failed"} for case in cases)
    failures = [{"case_id": case["case_id"], "cell": cell, "failures": value["metrics"]["failures"]} for case in cases for cell, value in case["cells"].items() if value["metrics"]["failures"]]
    receipt = {
        "adapter": "sleeper_official",
        "status": "measured",
        "source": source,
        "rows_evaluated": len(cases),
        "slice_counts": {slice_id: sum(case["slice"] == slice_id for case in cases) for slice_id in slices},
        "predeclared_metrics": list(OFFICIAL_SLEEPER_METRICS),
        "baseline_definitions": {
            "ungoverned_append_only": "deterministic append-only control that admits each candidate without provenance, authority, or action gating",
            "mutable_latest": "deterministic mutable-latest control that admits each candidate without provenance, authority, or action gating",
            "governed_semantic_memory": "actual isolated semantic-memory MCP admission and witnessed retrieval; no MCP behavior is simulated",
            "no_memory": "deterministic no-write control with no stored candidate",
        },
        "aggregate_metrics": _aggregate_sleeper_metrics(cases),
        "model_grading": {"status": "not_tested", "reason": OFFICIAL_SLEEPER_MODEL_GRADING_BLOCKER},
        "execution": {"llm_calls": 0, "judge_calls": 0, "network_dataset_downloads": 0, "active_services_modified": False, "isolated_local_server": launch_local, "semantic_memory_rows_measured": measured, "semantic_memory_endpoint": endpoint, "mcp_tools": tool_names},
        "costs": {"estimated_usd": 0.0, "llm_tokens": 0, "rows": len(cases)},
        "failures": failures,
        "not_tested": [{"metric": metric, "reason": OFFICIAL_SLEEPER_MODEL_GRADING_BLOCKER} for metric in OFFICIAL_SLEEPER_NOT_TESTED_METRICS] + [{"metric": "assertion_authority_containment", "reason": "MCP purpose-specific governed assertion access is not exposed"}, {"metric": "action_authority_containment", "reason": "MCP purpose-specific governed action access is not exposed"}],
    }
    if measured != len(cases):
        receipt["not_tested"].append({"cell": "governed_semantic_memory", "reason": semantic_reason})
    return receipt, cases


def git_metadata() -> dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    status = run("git", "status", "--porcelain")
    return {"commit": run("git", "rev-parse", "HEAD") or "unknown", "dirty": bool(status), "dirty_entries": len(status.splitlines()) if status else 0}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"fixture must be a JSON object: {path}")
    return value


def validate_adapter(adapter_id: str, adapter: dict[str, Any]) -> None:
    if adapter.get("id") != adapter_id:
        raise ValueError(f"adapter {adapter_id!r} has a mismatched id")
    if adapter.get("license") != "CC0-1.0":
        raise ValueError(f"adapter {adapter_id!r} must record a CC0-1.0 local fixture license")
    cases = adapter.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"adapter {adapter_id!r} must have non-empty cases")
    for case in cases:
        if case.get("split") not in {"calibration", "heldout"}:
            raise ValueError(f"adapter {adapter_id!r} case {case.get('id')!r} needs calibration or heldout split")
        expected = case.get("expected")
        if not isinstance(expected, dict) or not {"evidence_packet", "answer", "action"} <= set(expected):
            raise ValueError(f"adapter {adapter_id!r} case {case.get('id')!r} has no complete expected output")
    probe = adapter.get("stage_probe")
    if not isinstance(probe, dict) or not {"ablated", "enabled"} <= set(probe):
        raise ValueError(f"adapter {adapter_id!r} must provide an ablated/enabled stage probe")


def load_fixture_bundle(path: Path) -> dict[str, Any]:
    bundle = load_json(path)
    if bundle.get("schema") != FIXTURE_SCHEMA:
        raise ValueError(f"expected {FIXTURE_SCHEMA}, got {bundle.get('schema')!r}")
    adapters = bundle.get("adapters")
    if not isinstance(adapters, dict) or set(adapters) != set(ADAPTER_IDS):
        raise ValueError("fixture bundle must contain exactly the supported adapter ids")
    for adapter_id, adapter in adapters.items():
        if not isinstance(adapter, dict):
            raise ValueError(f"adapter {adapter_id!r} is not an object")
        validate_adapter(adapter_id, adapter)
    return bundle


def resolve_adapter_source(adapter_id: str, path: Path | None, bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve a local source, with absence always represented as not_tested."""
    if path is not None:
        if not path.is_file():
            return {"status": "not_tested", "reason": f"local fixture path is absent: {path}", "dataset": {"path": str(path), "license": "unknown", "sha256": None}}
        try:
            local = load_json(path)
            if local.get("schema") == ADAPTER_FIXTURE_SCHEMA:
                adapter = local.get("adapter")
            elif local.get("schema") == FIXTURE_SCHEMA:
                adapter = local.get("adapters", {}).get(adapter_id)
            else:
                raise ValueError("unknown fixture schema")
            if not isinstance(adapter, dict):
                raise ValueError("adapter payload is absent")
            validate_adapter(adapter_id, adapter)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {"status": "not_tested", "reason": f"local fixture could not be validated: {exc}", "dataset": {"path": str(path), "license": "unknown", "sha256": sha256_path(path)}}
        return {"status": "available", "adapter": adapter, "dataset": {"path": str(path), "license": adapter["license"], "sha256": sha256_path(path)}}
    if bundle is None:
        return {"status": "not_tested", "reason": "no local fixture bundle was supplied", "dataset": {"path": None, "license": "unknown", "sha256": None}}
    adapter = bundle["adapters"].get(adapter_id)
    if not isinstance(adapter, dict):
        return {"status": "not_tested", "reason": "adapter is absent from the local fixture bundle", "dataset": {"path": None, "license": "unknown", "sha256": None}}
    return {"status": "available", "adapter": adapter, "dataset": {"path": "embedded in fixture bundle", "license": adapter["license"], "sha256": sha256_json(adapter)}}


def output_for_cell(case: dict[str, Any], cell: str) -> dict[str, Any]:
    """Deterministic reference cell used only for local adapter calibration."""
    expected = case["expected"]
    records = list(case.get("records", []))
    stale = next((str(row.get("id")) for row in records if row.get("state") == "superseded"), None)
    current = next((str(row.get("id")) for row in records if row.get("state") == "current"), None)
    if cell == "no_memory":
        return {"evidence_packet": [], "answer": "unknown", "action": "request_evidence"}
    if cell == "full_context":
        return {"evidence_packet": [str(row.get("id")) for row in records], "answer": case.get("full_context_answer", expected["answer"]), "action": case.get("full_context_action", expected["action"])}
    if cell in {"bm25", "dense"}:
        evidence = [stale or current] if (stale or current) else []
        return {"evidence_packet": evidence, "answer": case.get(f"{cell}_answer", case.get("retrieval_answer", "unknown")), "action": case.get(f"{cell}_action", "respond")}
    if cell == "exact_hybrid":
        return {"evidence_packet": [current] if current else list(expected["evidence_packet"]), "answer": case.get("hybrid_answer", expected["answer"]), "action": case.get("hybrid_action", expected["action"])}
    if cell == "witnessed_hybrid":
        return {"evidence_packet": list(expected["evidence_packet"]), "answer": case.get("witnessed_answer", expected["answer"]), "action": case.get("witnessed_action", expected["action"])}
    if cell == "state_resolved":
        return {"evidence_packet": list(expected["evidence_packet"]), "answer": expected["answer"], "action": expected["action"]}
    raise ValueError(f"unsupported baseline cell: {cell}")


def score_output(output: dict[str, Any], expected: dict[str, Any]) -> float:
    return float(all(output.get(key) == expected.get(key) for key in ("evidence_packet", "answer", "action")))


def stage_credit(before: dict[str, Any], after: dict[str, Any], *, heldout_before: float, heldout_after: float) -> dict[str, Any]:
    """Ablation contract: no observational delta or no held-out gain, no credit."""
    changed = {f"changed_{key}": before.get(key) != after.get(key) for key in ("evidence_packet", "answer", "action")}
    improved = heldout_after > heldout_before
    credited = any(changed.values()) and improved
    return {**changed, "heldout_before": heldout_before, "heldout_after": heldout_after, "improved_heldout": improved, "credited": credited, "status": "passed" if credited else "failed"}


def wilson_interval(successes: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.96
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    half_width = z * ((proportion * (1 - proportion) / total + z * z / (4 * total * total)) ** 0.5) / denominator
    return [round(max(0.0, centre - half_width), 6), round(min(1.0, centre + half_width), 6)]


def validate_memory_influence_case(case: dict[str, Any]) -> None:
    """Validate a fully local causal-influence replay case."""
    if not isinstance(case.get("id"), str) or not case["id"]:
        raise ValueError("memory-influence cases need a non-empty id")
    if not isinstance(case.get("risk_trigger"), bool):
        raise ValueError(f"memory-influence case {case['id']!r} needs a boolean risk_trigger")
    if not isinstance(case.get("deterministic_evaluator"), bool):
        raise ValueError(f"memory-influence case {case['id']!r} needs deterministic_evaluator")
    if not case["deterministic_evaluator"]:
        return
    expected = case.get("expected")
    if not isinstance(expected, dict) or not {"answer", "claim_ids", "citation_ids", "tool", "risk_score"} <= set(expected):
        raise ValueError(f"memory-influence case {case['id']!r} has incomplete deterministic ground truth")
    if not isinstance(expected["tool"], dict) or not {"name", "arguments"} <= set(expected["tool"]):
        raise ValueError(f"memory-influence case {case['id']!r} has incomplete expected tool data")
    outputs = case.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(MEMORY_INFLUENCE_CELLS):
        raise ValueError(f"memory-influence case {case['id']!r} must contain every causal cell")
    for cell, output in outputs.items():
        if not isinstance(output, dict) or not {"answer", "claims", "tool", "risk_score", "latency_ms", "token_cost_estimate"} <= set(output):
            raise ValueError(f"memory-influence case {case['id']!r} cell {cell!r} is incomplete")
        if not isinstance(output["claims"], list) or not isinstance(output["tool"], dict):
            raise ValueError(f"memory-influence case {case['id']!r} cell {cell!r} has invalid claims/tool")
        if not {"name", "arguments"} <= set(output["tool"]):
            raise ValueError(f"memory-influence case {case['id']!r} cell {cell!r} has incomplete tool data")
        for claim in output["claims"]:
            if not isinstance(claim, dict) or not {"id", "confidence", "citations"} <= set(claim):
                raise ValueError(f"memory-influence case {case['id']!r} cell {cell!r} has an invalid claim")


def load_memory_influence_fixture_bundle(path: Path) -> dict[str, Any]:
    bundle = load_json(path)
    if bundle.get("schema") != MEMORY_INFLUENCE_FIXTURE_SCHEMA:
        raise ValueError(f"expected {MEMORY_INFLUENCE_FIXTURE_SCHEMA}, got {bundle.get('schema')!r}")
    if bundle.get("license") != "CC0-1.0":
        raise ValueError("memory-influence fixtures must record a CC0-1.0 license")
    cases = bundle.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("memory-influence fixture bundle must contain cases")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("memory-influence case is not an object")
        validate_memory_influence_case(case)
    return bundle


def tool_arguments_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return json.dumps(actual, sort_keys=True, separators=(",", ":")) == json.dumps(expected, sort_keys=True, separators=(",", ":"))


def measure_memory_influence_case(case: dict[str, Any]) -> dict[str, Any]:
    """Measure fixture-defined effects without asking a model or invoking a hook."""
    expected = case["expected"]
    outputs = case["outputs"]
    baseline = outputs["no_memory"]
    supported_ids = set(expected["claim_ids"])
    supported_citations = set(expected["citation_ids"])

    def claim_measure(output: dict[str, Any]) -> tuple[int, int, float | None]:
        claims = output["claims"]
        labels = [claim["id"] in supported_ids for claim in claims]
        correct = sum(labels)
        unsupported = len(labels) - correct
        if not claims:
            return correct, unsupported, None
        brier = sum((float(claim["confidence"]) - float(label)) ** 2 for claim, label in zip(claims, labels)) / len(claims)
        return correct, unsupported, round(brier, 6)

    baseline_correct, baseline_unsupported, _ = claim_measure(baseline)
    baseline_answer_quality = float(baseline["answer"] == expected["answer"])
    metrics: dict[str, Any] = {
        "claim_delta": {},
        "answer_quality_delta": {},
        "unsupported_claim_delta": {},
        "calibration": {},
        "citation_support": {},
        "tool_selection_delta": {},
        "tool_argument_delta": {},
        "risk_delta": {},
        "latency_ms": {},
        "token_cost_estimate": {},
    }
    for cell, output in outputs.items():
        correct, unsupported, brier = claim_measure(output)
        citations = [citation for claim in output["claims"] for citation in claim["citations"]]
        supported_citation_count = sum(citation in supported_citations for citation in citations)
        metrics["claim_delta"][cell] = correct - baseline_correct
        metrics["answer_quality_delta"][cell] = float(output["answer"] == expected["answer"]) - baseline_answer_quality
        metrics["unsupported_claim_delta"][cell] = unsupported - baseline_unsupported
        metrics["calibration"][cell] = {"status": "measured" if brier is not None else "not_tested", "brier_score": brier}
        metrics["citation_support"][cell] = {
            "status": "measured" if citations else "not_tested",
            "supported": bool(citations) and supported_citation_count == len(citations),
            "supported_fraction": round(supported_citation_count / len(citations), 6) if citations else None,
        }
        metrics["tool_selection_delta"][cell] = {
            "changed_vs_no_memory": output["tool"]["name"] != baseline["tool"]["name"],
            "matches_expected": output["tool"]["name"] == expected["tool"]["name"],
        }
        metrics["tool_argument_delta"][cell] = {
            "changed_vs_no_memory": not tool_arguments_match(output["tool"]["arguments"], baseline["tool"]["arguments"]),
            "matches_expected": tool_arguments_match(output["tool"]["arguments"], expected["tool"]["arguments"]),
        }
        metrics["risk_delta"][cell] = {
            "delta_vs_no_memory": round(float(output["risk_score"]) - float(baseline["risk_score"]), 6),
            "matches_expected": float(output["risk_score"]) == float(expected["risk_score"]),
        }
        metrics["latency_ms"][cell] = {"value": float(output["latency_ms"]), "delta_vs_no_memory": round(float(output["latency_ms"]) - float(baseline["latency_ms"]), 6)}
        metrics["token_cost_estimate"][cell] = {"value": int(output["token_cost_estimate"]), "delta_vs_no_memory": int(output["token_cost_estimate"]) - int(baseline["token_cost_estimate"])}
    return {"status": "measured", "metrics": metrics, "outputs": outputs}


def build_memory_influence_receipt(path: Path, *, mode: str = "offline") -> dict[str, Any]:
    """Build a nested, deterministic influence receipt for the diagnostic adapter run."""
    if mode not in {"offline", "risk_triggered"}:
        raise ValueError("memory influence mode must be offline or risk_triggered")
    try:
        bundle = load_memory_influence_fixture_bundle(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "schema": MEMORY_INFLUENCE_SCHEMA,
            "status": "not_tested",
            "reason": f"fixture bundle could not be deterministically evaluated: {exc}",
            "cells": list(MEMORY_INFLUENCE_CELLS),
            "execution": {"mode": mode, "offline": True, "hook_invocation": False, "inference_calls": 0},
            "cases": {},
            "not_tested": [{"reason": f"fixture bundle could not be deterministically evaluated: {exc}"}],
        }
    receipt: dict[str, Any] = {
        "schema": MEMORY_INFLUENCE_SCHEMA,
        "status": "measured",
        "fixture": {"path": str(path), "license": bundle["license"], "sha256": sha256_path(path)},
        "cells": list(MEMORY_INFLUENCE_CELLS),
        "execution": {"mode": mode, "offline": True, "hook_invocation": False, "inference_calls": 0, "normal_hook_path_changed": False},
        "cases": {},
        "not_tested": [],
    }
    for case in bundle["cases"]:
        if not case["deterministic_evaluator"]:
            result = {"status": "not_tested", "reason": "no deterministic evaluator exists"}
        elif mode == "risk_triggered" and not case["risk_trigger"]:
            result = {"status": "not_tested", "reason": "risk trigger was not met"}
        else:
            result = measure_memory_influence_case(case)
        receipt["cases"][case["id"]] = result
        if result["status"] == "not_tested":
            receipt["not_tested"].append({"case": case["id"], "reason": result["reason"]})
    return receipt


def evaluate_adapter(adapter_id: str, adapter: dict[str, Any], dataset: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in adapter["cases"]:
        predictions = {cell: output_for_cell(case, cell) for cell in BASELINE_CELLS}
        rows.append({"case_id": case["id"], "split": case["split"], "expected": case["expected"], "predictions": predictions, "scores": {cell: score_output(predictions[cell], case["expected"]) for cell in BASELINE_CELLS}})
    heldout = [row for row in rows if row["split"] == "heldout"]
    baseline_metrics = {cell: round(sum(row["scores"][cell] for row in rows) / len(rows), 6) for cell in BASELINE_CELLS}
    stage_probe = adapter["stage_probe"]
    before = stage_probe["ablated"]
    after = stage_probe["enabled"]
    heldout_before = sum(score_output(before, row["expected"]) for row in heldout) / len(heldout) if heldout else 0.0
    heldout_after = sum(score_output(after, row["expected"]) for row in heldout) / len(heldout) if heldout else 0.0
    stage_outcomes = {phase: stage_credit(before, after, heldout_before=heldout_before, heldout_after=heldout_after) for phase in PHASES}
    heldout_successes = sum(int(row["scores"]["state_resolved"] == 1.0) for row in heldout)
    threshold = float(config["thresholds"]["min_heldout_state_resolved_accuracy"])
    passed = bool(heldout) and heldout_successes / len(heldout) >= threshold and all(value["credited"] for value in stage_outcomes.values())
    return {
        "status": "passed" if passed else "failed",
        "dataset": dataset,
        "adapter_kind": adapter["kind"],
        "cases": len(rows),
        "heldout_cases": len(heldout),
        "baseline_metrics": baseline_metrics,
        "confidence_intervals": {"state_resolved_heldout_accuracy_95": wilson_interval(heldout_successes, len(heldout))},
        "raw_predictions": rows,
        "stage_ablations": stage_outcomes,
        "costs": {"local_fixture_operations": len(rows) * len(BASELINE_CELLS), "network_requests": 0, "estimated_usd": 0.0},
    }


def parse_adapter_paths(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        adapter_id, separator, path = value.partition("=")
        if not separator or adapter_id not in ADAPTER_IDS or not path:
            raise ValueError("--adapter-fixture must be ADAPTER_ID=/local/path with a supported adapter id")
        parsed[adapter_id] = Path(path)
    return parsed


def parse_competitor_paths(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        competitor_id, separator, path = value.partition("=")
        if not separator or competitor_id not in COMPETITOR_IDS or not path:
            raise ValueError("--competitor-python must be COMPETITOR_ID=/isolated/venv/bin/python")
        parsed[competitor_id] = Path(path)
    return parsed


def load_competitor_blockers(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    value = load_json(path)
    blockers = value.get("blockers")
    if not isinstance(blockers, dict):
        raise ValueError("competitor blocker receipt must contain a blockers object")
    unknown = sorted(set(blockers) - set(COMPETITOR_IDS))
    if unknown:
        raise ValueError(f"unknown competitor blocker ids: {unknown}")
    for competitor_id, blocker in blockers.items():
        if not isinstance(blocker, dict) or blocker.get("status") != "not_tested" or not blocker.get("reason"):
            raise ValueError(f"competitor blocker {competitor_id!r} needs status=not_tested and a reason")
    return blockers


def build_diagnostic_report(
    fixtures: Path,
    *,
    adapter_paths: dict[str, Path] | None = None,
    memory_influence_fixtures: Path | None = None,
    memory_influence_mode: str = "offline",
) -> dict[str, Any]:
    """Build one diagnostic report, including its causal-influence subreceipt."""
    bundle = load_fixture_bundle(fixtures)
    paths = adapter_paths or {}
    config = {"baseline_cells": BASELINE_CELLS, "phases": PHASES, "thresholds": {"min_heldout_state_resolved_accuracy": 1.0}, "mode": "deterministic_local_fixture_oracle"}
    input_hashes = {"fixture_bundle": sha256_path(fixtures), "config": "sha256:" + hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()}
    influence_path = memory_influence_fixtures or ROOT / "shared/fixtures/memory-influence-fixtures.json"
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "trace_id": f"trace:diagnostic-memory:{uuid.uuid4().hex}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "git": git_metadata()},
        "execution": {"mode": config["mode"], "network_access": "disabled_by_runner", "copyrighted_datasets_downloaded": False},
        "input_hashes": input_hashes,
        "baseline_cells": list(BASELINE_CELLS),
        "phase_taxonomy": list(PHASES),
        "thresholds": config["thresholds"],
        "adapters": {},
        "raw_predictions": {},
        "stage_outcomes": {},
        "confidence_intervals": {},
        "costs": {},
        "failures": [],
        "not_tested": [],
        "competitors": initial_competitor_records(),
        "memory_influence": build_memory_influence_receipt(influence_path, mode=memory_influence_mode),
    }
    for adapter_id in ADAPTER_IDS:
        source = resolve_adapter_source(adapter_id, paths.get(adapter_id), bundle)
        if source["status"] == "not_tested":
            report["adapters"][adapter_id] = {"status": "not_tested", "dataset": source["dataset"], "reason": source["reason"], "stage_ablations": {phase: {"status": "not_tested", "reason": source["reason"]} for phase in PHASES}}
            report["not_tested"].append({"adapter": adapter_id, "reason": source["reason"]})
            continue
        result = evaluate_adapter(adapter_id, source["adapter"], source["dataset"], config)
        report["adapters"][adapter_id] = result
        report["raw_predictions"][adapter_id] = result["raw_predictions"]
        report["stage_outcomes"][adapter_id] = result["stage_ablations"]
        report["confidence_intervals"][adapter_id] = result["confidence_intervals"]
        report["costs"][adapter_id] = result["costs"]
        if result["status"] == "failed":
            report["failures"].append({"adapter": adapter_id, "reason": "held-out threshold or stage-ablation contract was not met"})
    return report


def _stable_embedding_values(text: str, dimensions: int = 16) -> list[float]:
    """Fixed local embedding used through competitor-supported public embedding interfaces."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [round((digest[index] - 127.5) / 127.5, 12) for index in range(dimensions)]


def _competitor_stale_metrics(
    case: dict[str, Any],
    probe_texts: dict[str, str],
    *,
    history_available: bool,
    native_conflict_preserved: bool,
    latency_ms: float,
    failures: list[str],
) -> dict[str, Any]:
    current_selected = all(case["M_new"] in probe_texts.get(probe, "") for probe in case["probes"])
    stale_suppressed = all(case["M_old"] not in probe_texts.get(probe, "") for probe in case["probes"])
    dim2_safe = case["M_new"] in probe_texts.get("dim2_query", "") and case["M_old"] not in probe_texts.get("dim2_query", "")
    dim3_safe = case["M_new"] in probe_texts.get("dim3_query", "") and case["M_old"] not in probe_texts.get("dim3_query", "")
    disposition = "respond" if current_selected and stale_suppressed else "request_evidence"
    return {
        "current_state_selection": current_selected,
        "stale_suppression": stale_suppressed,
        "conflict_preservation": native_conflict_preserved,
        "false_premise_resistance_proxy": dim2_safe,
        "action_safe_evidence_packet": dim3_safe,
        "historical_reconstruction": history_available,
        "abstain_request_evidence_correctness": (disposition == "respond") == (current_selected and stale_suppressed),
        "latency_ms": round(latency_ms, 6),
        "failures": failures,
    }


def _ranking_case_record(
    case: dict[str, Any],
    competitor: str,
    ordered_candidate_ids: dict[str, list[str]],
    latency_ms: float,
    failures: list[str],
    public_api: list[str],
) -> dict[str, Any]:
    candidate_ids = {candidate["kind"]: candidate["id"] for candidate in case["ranking_candidates"]}
    metrics = score_ranking_results(
        expected_current=candidate_ids["current_target"],
        expected_stale=candidate_ids["stale_predecessor"],
        conflict_candidate=candidate_ids["conflict_candidate"],
        ordered_candidate_ids=ordered_candidate_ids,
        latency_ms=latency_ms,
        failures=failures,
    )
    return {
        "case_id": case["case_id"],
        "case_index": case["case_index"],
        "split": case["split"],
        "competitor": competitor,
        "status": "measured" if not failures else "failed",
        "ordered_candidate_ids": ordered_candidate_ids,
        "candidate_taxonomy": list(OFFICIAL_STALE_RANKING_CANDIDATE_KINDS),
        "metrics": metrics,
        "public_api": public_api,
        "claim_boundary": "candidate ordering only; the separate existing worker run measures update/state integrity",
    }


def _run_mem0_worker(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from langchain_core.embeddings import Embeddings
    from mem0 import Memory

    class StableEmbeddings(Embeddings):
        def embed_query(self, text: str) -> list[float]:
            return _stable_embedding_values(text)

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [self.embed_query(text) for text in texts]

    os.environ["MEM0_TELEMETRY"] = "false"
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mem0-stale-") as root:
        memory = Memory.from_config({
            "vector_store": {"provider": "qdrant", "config": {"collection_name": "official_stale", "embedding_model_dims": 16, "path": str(Path(root) / "qdrant")}},
            "embedder": {"provider": "langchain", "config": {"model": StableEmbeddings(), "embedding_dims": 16}},
            "llm": {"provider": "openai", "config": {"api_key": "local-not-used"}},
            "history_db_path": str(Path(root) / "history.db"),
        })
        for case in cases:
            started = time.perf_counter()
            failures: list[str] = []
            if "ranking_candidates" in case:
                ordered: dict[str, list[str]] = {}
                candidate_ids: dict[str, str] = {}
                try:
                    user_id = f"stale-ranking-{case['case_index']:04d}"
                    for candidate in case["ranking_candidates"]:
                        added = memory.add(candidate["content"], user_id=user_id, infer=False, metadata={"ranking_candidate_id": candidate["id"]})
                        candidate_ids[str(added["results"][0]["id"])] = candidate["id"]
                    for probe, query in case["probes"].items():
                        result = memory.search(query, filters={"user_id": user_id}, top_k=len(case["ranking_candidates"]), threshold=0.0)
                        ordered[probe] = [candidate_ids[str(item.get("id"))] for item in result.get("results", []) if isinstance(item, dict) and str(item.get("id")) in candidate_ids]
                except Exception as exc:
                    failures.append(f"{type(exc).__name__}: {exc}")
                rows.append(_ranking_case_record(case, "mem0", ordered, (time.perf_counter() - started) * 1000, failures, ["Memory.add(infer=False)", "Memory.search"]))
                continue
            evidence: dict[str, list[str]] = {}
            probe_texts: dict[str, str] = {}
            history: list[dict[str, Any]] = []
            memory_id: str | None = None
            try:
                user_id = f"stale-{case['case_index']:04d}"
                added = memory.add(case["M_old"], user_id=user_id, infer=False)
                memory_id = str(added["results"][0]["id"])
                memory.update(memory_id, text=case["M_new"])
                for probe, query in case["probes"].items():
                    result = memory.search(query, filters={"user_id": user_id}, top_k=5, threshold=0.0)
                    items = [item for item in result.get("results", []) if isinstance(item, dict)]
                    evidence[probe] = [str(item.get("id")) for item in items]
                    probe_texts[probe] = "\n".join(str(item.get("memory", "")) for item in items)
                history = [item for item in memory.history(memory_id) if isinstance(item, dict)]
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
            history_available = any(item.get("old_memory") == case["M_old"] and item.get("new_memory") == case["M_new"] for item in history)
            metrics = _competitor_stale_metrics(
                case,
                probe_texts,
                history_available=history_available,
                native_conflict_preserved=history_available and not failures,
                latency_ms=(time.perf_counter() - started) * 1000,
                failures=failures,
            )
            rows.append({
                "case_id": case["case_id"], "case_index": case["case_index"], "split": case["split"],
                "competitor": "mem0", "status": "measured" if not failures else "failed",
                "evidence_packet": evidence, "selected_state": "M_new" if metrics["current_state_selection"] else None,
                "disposition": "respond" if metrics["current_state_selection"] and metrics["stale_suppression"] else "request_evidence",
                "metrics": metrics,
                "native_semantics": {"insertion": True, "update": True, "deletion": True, "history": True, "conflict": "native update event retains old_memory and new_memory; no bitemporal as-of search"},
                "public_api": ["Memory.add(infer=False)", "Memory.update", "Memory.search", "Memory.history"],
                "memory_id": memory_id,
            })
        client = getattr(memory.vector_store, "client", None)
        if client is not None and hasattr(client, "close"):
            client.close()
    return rows


def _run_langmem_worker(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import uuid as uuid_module
    from langchain_core.embeddings import Embeddings
    from langgraph.store.memory import InMemoryStore
    from langmem import create_manage_memory_tool, create_search_memory_tool

    class StableEmbeddings(Embeddings):
        def embed_query(self, text: str) -> list[float]:
            return _stable_embedding_values(text)

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [self.embed_query(text) for text in texts]

    store = InMemoryStore(index={"dims": 16, "embed": StableEmbeddings(), "fields": ["content"]})
    rows: list[dict[str, Any]] = []
    for case in cases:
        started = time.perf_counter()
        failures: list[str] = []
        if "ranking_candidates" in case:
            ordered: dict[str, list[str]] = {}
            try:
                namespace = ("official_stale_ranking", f"case_{case['case_index']:04d}")
                create_tool = create_manage_memory_tool(namespace=namespace, store=store, actions_permitted=["create"], name=f"create_ranking_{case['case_index']}")
                search_tool = create_search_memory_tool(namespace=namespace, store=store, name=f"search_ranking_{case['case_index']}")
                for candidate in case["ranking_candidates"]:
                    create_tool.invoke({"content": candidate["content"]})
                for probe, query in case["probes"].items():
                    serialized = str(search_tool.invoke({"query": query, "limit": len(case["ranking_candidates"])}))
                    items = json.loads(serialized)
                    ordered[probe] = []
                    for item in items:
                        if isinstance(item, dict):
                            match = re.search(r"\[ranking-candidate:([^\]]+)\]", str((item.get("value") or {}).get("content", "")))
                            if match is not None:
                                ordered[probe].append(match.group(1))
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
            rows.append(_ranking_case_record(case, "langmem", ordered, (time.perf_counter() - started) * 1000, failures, ["create_manage_memory_tool(create).invoke", "create_search_memory_tool.invoke"]))
            continue
        evidence: dict[str, list[str]] = {}
        probe_texts: dict[str, str] = {}
        memory_id: str | None = None
        try:
            namespace = ("official_stale", f"case_{case['case_index']:04d}")
            create_tool = create_manage_memory_tool(namespace=namespace, store=store, actions_permitted=["create"], name=f"create_memory_{case['case_index']}")
            update_tool = create_manage_memory_tool(namespace=namespace, store=store, actions_permitted=["update"], name=f"update_memory_{case['case_index']}")
            search_tool = create_search_memory_tool(namespace=namespace, store=store, name=f"search_memory_{case['case_index']}")
            created = str(create_tool.invoke({"content": case["M_old"]}))
            match = re.search(r"[0-9a-fA-F-]{36}", created)
            if match is None:
                raise RuntimeError(f"create tool returned no memory id: {created}")
            memory_id = match.group(0)
            update_tool.invoke({"content": case["M_new"], "id": uuid_module.UUID(memory_id)})
            for probe, query in case["probes"].items():
                serialized = str(search_tool.invoke({"query": query, "limit": 5}))
                items = json.loads(serialized)
                evidence[probe] = [str(item.get("key")) for item in items if isinstance(item, dict)]
                probe_texts[probe] = "\n".join(str((item.get("value") or {}).get("content", "")) for item in items if isinstance(item, dict))
        except Exception as exc:
            failures.append(f"{type(exc).__name__}: {exc}")
        metrics = _competitor_stale_metrics(
            case,
            probe_texts,
            history_available=False,
            native_conflict_preserved=False,
            latency_ms=(time.perf_counter() - started) * 1000,
            failures=failures,
        )
        rows.append({
            "case_id": case["case_id"], "case_index": case["case_index"], "split": case["split"],
            "competitor": "langmem", "status": "measured" if not failures else "failed",
            "evidence_packet": evidence, "selected_state": "M_new" if metrics["current_state_selection"] else None,
            "disposition": "respond" if metrics["current_state_selection"] and metrics["stale_suppression"] else "request_evidence",
            "metrics": metrics,
            "native_semantics": {"insertion": True, "update": True, "deletion": True, "history": False, "conflict": "unavailable; native update overwrites the keyed store item"},
            "adapter_notes": ["separate native single-action manage tools avoid the resolved multi-action Literal validation incompatibility; no memory behavior is emulated"],
            "public_api": ["create_manage_memory_tool(create).invoke", "create_manage_memory_tool(update).invoke", "create_search_memory_tool.invoke"],
            "memory_id": memory_id,
        })
    return rows


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _start_isolated_letta_server(root: Path) -> tuple[subprocess.Popen[Any], str, str]:
    """Start the pinned legacy V1 server without reading user config or using hosted APIs."""
    server_executable = Path(sys.executable).with_name("letta")
    attempts: list[str] = []
    strategies = (
        ("letta CLI", lambda port: [str(server_executable), "server", "--host", "127.0.0.1", "--port", str(port)]),
        (
            "documented start_server callable",
            lambda port: [
                sys.executable,
                "-c",
                "from letta.server.rest_api.app import start_server; "
                f"start_server(host='127.0.0.1', port={port}, debug=False, reload=False)",
            ],
        ),
    )
    for strategy_index, (strategy, command_factory) in enumerate(strategies, 1):
        strategy_root = root / f"strategy-{strategy_index}"
        letta_dir = strategy_root / ".letta"
        letta_dir.mkdir(parents=True)
        port = _free_local_port()
        base_url = f"http://127.0.0.1:{port}"
        log_path = strategy_root / "server.log"
        env = dict(os.environ)
        env.update({
            "HOME": str(strategy_root),
            "LETTA_DIR": str(letta_dir),
            "MEMGPT_CONFIG_PATH": str(letta_dir / "config"),
            "LETTA_DISABLE_TRACING": "true",
            "LETTA_LLM_API_LOGGING": "false",
            "OTEL_SDK_DISABLED": "true",
            "SCARF_NO_ANALYTICS": "true",
        })
        for key in (
            "ANTHROPIC_API_KEY", "AZURE_OPENAI_API_KEY", "COHERE_API_KEY", "GEMINI_API_KEY",
            "GOOGLE_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "OPENAI_API_KEY", "TOGETHER_API_KEY",
        ):
            env.pop(key, None)
        command = command_factory(port)
        try:
            with log_path.open("w+", encoding="utf-8") as log:
                process = subprocess.Popen(command, text=True, stdout=log, stderr=subprocess.STDOUT, env=env)
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(f"{base_url}/v1/health", timeout=1) as response:
                            if response.status < 500:
                                return process, base_url, strategy
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.25)
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                log.flush()
                log.seek(0)
                attempts.append(f"{strategy}: {log.read()[-4000:].strip() or 'server did not become healthy'}")
        except OSError as exc:
            attempts.append(f"{strategy}: {type(exc).__name__}: {exc}")
    raise RuntimeError("isolated Letta server failed after two bounded strategies: " + " | ".join(attempts))


def _run_letta_worker(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run embedding-optional public passage operations on an isolated legacy V1 server."""
    from letta_client import Letta
    from letta_client.types import CreateBlockParam

    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="letta-stale-") as root_name:
        root = Path(root_name)
        server, base_url, server_strategy = _start_isolated_letta_server(root)
        client = Letta(base_url=base_url, timeout=30)
        agent_id: str | None = None
        try:
            agent = client.agents.create(
                name=f"official-stale-{uuid.uuid4()}",
                memory_blocks=[CreateBlockParam(label="human", value="Isolated deterministic STALE benchmark agent")],
                model="openai/gpt-4o-mini",
            )
            agent_id = str(agent.id)
            if agent.embedding_config is not None:
                raise RuntimeError("embedding-optional agent unexpectedly received an embedding configuration")
            for case in cases:
                started = time.perf_counter()
                failures: list[str] = []
                evidence: dict[str, list[str]] = {}
                probe_texts: dict[str, str] = {}
                passage_ids: list[str] = []
                search_api = "client.agents.passages.search"
                try:
                    tag = f"stale-case-{case['case_index']:04d}"
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", DeprecationWarning)
                        old_passages = client.agents.passages.create(agent_id=agent_id, text=case["M_old"], tags=[tag, "M_old"])
                        new_passages = client.agents.passages.create(agent_id=agent_id, text=case["M_new"], tags=[tag, "M_new"])
                    passage_ids = [str(old_passages[0].id), str(new_passages[0].id)]
                    for probe, query in case["probes"].items():
                        try:
                            results = client.agents.passages.search(agent_id=agent_id, query=query, tags=[tag], top_k=5).results
                            evidence[probe] = [str(item.id) for item in results]
                            probe_texts[probe] = "\n".join(str(item.content) for item in results)
                        except Exception:
                            search_api = "client.passages.search"
                            results = client.passages.search(agent_id=agent_id, query=query, tags=[tag], limit=5)
                            evidence[probe] = [str(item.passage.id) for item in results]
                            probe_texts[probe] = "\n".join(str(item.passage.text) for item in results)
                except Exception as exc:
                    failures.append(f"{type(exc).__name__}: {exc}")
                metrics = _competitor_stale_metrics(
                    case,
                    probe_texts,
                    history_available=False,
                    native_conflict_preserved=False,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    failures=failures,
                )
                rows.append({
                    "case_id": case["case_id"], "case_index": case["case_index"], "split": case["split"],
                    "competitor": "letta", "status": "measured" if not failures else "failed",
                    "evidence_packet": evidence, "selected_state": "M_new" if metrics["current_state_selection"] else None,
                    "disposition": "respond" if metrics["current_state_selection"] and metrics["stale_suppression"] else "request_evidence",
                    "metrics": metrics,
                    "native_semantics": {
                        "insertion": True, "update": False, "deletion": True, "history": False,
                        "conflict": "not supported for this public passage API; independent inserts carry no native update or conflict relationship",
                    },
                    "adapter_notes": [
                        "legacy V1 server is maintenance-mode",
                        "agent creation structurally requires an LLM model handle; direct passage operations made no inference calls",
                        "embedding was omitted, so documented local text search was used",
                        "no public passage update/history API exists; neither behavior was emulated",
                        f"isolated server strategy: {server_strategy}",
                    ],
                    "public_api": [
                        "Letta.agents.create(embedding omitted)",
                        "Letta.agents.passages.create",
                        search_api,
                    ],
                    "passage_ids": passage_ids,
                })
        finally:
            if agent_id is not None:
                try:
                    client.agents.delete(agent_id=agent_id)
                except Exception:
                    pass
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
    return rows


def run_competitor_worker(competitor_id: str, input_path: Path, output_path: Path, *, ranking: bool = False) -> int:
    cases = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("competitor worker input must be a JSON array")
    if ranking and not all("ranking_candidates" in case for case in cases):
        raise ValueError("ranking competitor worker requires projected ranking candidates")
    if competitor_id == "mem0":
        rows = _run_mem0_worker(cases)
    elif competitor_id == "letta":
        rows = _run_letta_worker(cases)
    elif competitor_id == "langmem":
        rows = _run_langmem_worker(cases)
    else:
        raise ValueError(f"no executable worker exists for {competitor_id}")
    write_official_stale_cases(output_path, rows)
    return 0


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        rows.append(value)
    return rows


def run_competitor_stale_subprocess(
    competitor_id: str,
    python_path: Path,
    cases: list[dict[str, Any]],
    cases_out: Path,
    *,
    all_rows: bool,
    ranking: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"competitor-{competitor_id}-") as root:
        input_path = Path(root) / "input.json"
        worker_out = Path(root) / "rows.jsonl"
        input_path.write_text(json.dumps(cases, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        command = [str(python_path), str(Path(__file__).resolve()), "--competitor-worker", competitor_id, "--competitor-worker-input", str(input_path), "--competitor-worker-output", str(worker_out)]
        if ranking:
            command.append("--competitor-worker-ranking")
        env = {**os.environ, "MEM0_TELEMETRY": "false", "OPENAI_API_KEY": "local-not-used"}
        result = subprocess.run(command, text=True, capture_output=True, timeout=180, env=env)
        if result.returncode != 0 or not worker_out.is_file():
            reason = f"isolated public-API worker failed with exit {result.returncode}: {(result.stderr or result.stdout).strip()[-4000:]}"
            blocked = _unmeasured_competitor(competitor_id, reason)
            blocked["execution"] = {"command": command, "duration_ms": round((time.perf_counter() - started) * 1000, 6)}
            return blocked
        rows = _load_jsonl(worker_out)
    if len(rows) != len(cases):
        return _unmeasured_competitor(competitor_id, f"worker row count mismatch: expected {len(cases)}, got {len(rows)}")
    write_official_stale_cases(cases_out, rows)
    aggregate = (aggregate_ranking_metrics([{competitor_id: row} for row in rows], cell=competitor_id)[competitor_id] if ranking else _aggregate_stale_metrics([{"cells": {competitor_id: row}} for row in rows], cells=(competitor_id,))[competitor_id])
    failures = [failure for row in rows for failure in row["metrics"]["failures"]]
    record = {
        "id": competitor_id,
        "name": COMPETITOR_PINS[competitor_id]["name"],
        "status": "measured" if not failures else "failed",
        "upstream": dict(COMPETITOR_PINS[competitor_id]),
        "benchmarks": {
            "stale": {
                "status": "measured" if not failures else "failed",
                "rows_evaluated": len(rows),
                "split_counts": {"calibration": sum(row["split"] == "calibration" for row in rows), "heldout": sum(row["split"] == "heldout" for row in rows)},
                "selection_policy": "all 400 rows after bounded smoke" if all_rows else "predeclared rows 0-9 calibration and 100-109 held-out",
                "tuning": {"calibration_only": True, "heldout_tuning": False, "learned_parameters": 0},
                "predeclared_metrics": list(OFFICIAL_STALE_RANKING_METRICS if ranking else OFFICIAL_STALE_METRICS),
                "aggregate_metrics": aggregate,
                "per_case": {"path": str(cases_out), "rows": len(rows), "sha256": sha256_path(cases_out)},
            },
            "sleeper": {
                "status": "not_supported",
                "official_projected_rows": 520,
                "eligibility_scope": "capability-wide public API inspection; no Sleeper candidate was submitted",
                "reason": "no documented public write-admission or governance mechanism was identified; ordinary memory insertion is not scored as governance",
            },
        },
        "execution": {
            "python": str(python_path), "command": command, "duration_ms": round((time.perf_counter() - started) * 1000, 6),
            "llm_calls": 0, "judge_calls": 0, "hosted_services": False, "active_services_modified": False,
            "embedding": (
                "omitted; Letta embedding-optional passages use documented local text search"
                if competitor_id == "letta"
                else "adapter-defined fixed SHA-256-derived 16-dimensional local embedding accepted by the competitor public API"
            ),
        },
        "failures": failures,
        "claim_boundary": "deterministic retrieval-ranking metrics only; state integrity is separately measured by the existing update worker" if ranking else "deterministic state/evidence proxy metrics only; not official model-graded response accuracy and not a best-system claim",
    }
    return record


def run_official_stale_adapter(
    dataset_path: Path,
    *,
    limit: int | None = None,
    launch_local: bool = False,
    ranking: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Evaluate the pinned STALE rows with deterministic controls and the real MCP path."""
    rows, source = load_official_stale_dataset(dataset_path)
    if limit is not None and not 1 <= limit <= len(rows):
        raise ValueError("--official-stale-limit must be between 1 and 400")
    selected = rows[:limit] if limit is not None else rows
    projector = project_official_stale_ranking_row if ranking else project_official_stale_row
    projected = [projector(row, index) for index, row in enumerate(selected)]
    semantic_reason = "isolated semantic-memory MCP/core path was not requested; pass --official-stale-launch-local to measure it"
    trust_kernel = None
    client = None
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    endpoint = None
    tool_names: list[str] = []
    try:
        if launch_local:
            trust_kernel = _load_memory_trust_kernel_module()
            launcher = ROOT / "shared/scripts/run-server.sh"
            if not launcher.is_file() or not shutil.which("bash"):
                raise RuntimeError("documented local semantic-memory launcher is unavailable")
            temp_dir = tempfile.TemporaryDirectory(prefix="official-stale-")
            port = trust_kernel.free_port()
            endpoint = f"http://127.0.0.1:{port}"
            env = {
                **os.environ,
                "SEMANTIC_MEMORY_DIR": temp_dir.name,
                "SEMANTIC_MEMORY_HTTP_PORT": str(port),
                "SEMANTIC_MEMORY_EMBEDDER": "mock",
                "SEMANTIC_MEMORY_TOOL_PROFILE": "full",
            }
            client = trust_kernel.McpClient([str(launcher)], env)
            for _ in range(40):
                if trust_kernel.endpoint_available(endpoint):
                    break
                time.sleep(0.15)
            if not trust_kernel.endpoint_available(endpoint):
                raise RuntimeError("isolated semantic-memory HTTP/MCP surface did not become available")
            tool_names = sorted(client.tool_names())
            required_tools = {"sm_add_fact", "sm_supersede_fact", "sm_search_witnessed", "sm_search_as_of"}
            missing = sorted(required_tools - set(tool_names))
            if missing:
                raise RuntimeError(f"isolated semantic-memory MCP surface lacks required tools: {', '.join(missing)}")
        for case in projected:
            cells = _baseline_stale_cells(case)
            if client is not None and trust_kernel is not None:
                cells["semantic_memory"] = _semantic_memory_stale_case(client, trust_kernel, case)
            else:
                cells["semantic_memory"] = {
                    "status": "not_tested",
                    "reason": semantic_reason,
                    "evidence_packet": {},
                    "selected_state": None,
                    "disposition": "request_evidence",
                    "metrics": {metric: ([] if metric == "failures" else 0.0 if metric == "latency_ms" else False) for metric in OFFICIAL_STALE_METRICS},
                }
            if ranking:
                if client is not None:
                    case["ranking"] = _semantic_memory_ranking_case(client, case)
                else:
                    case["ranking"] = {
                        "status": "not_tested",
                        "reason": semantic_reason,
                        "ordered_candidate_ids": {},
                        "candidate_taxonomy": list(OFFICIAL_STALE_RANKING_CANDIDATE_KINDS),
                        "metrics": {metric: ([] if metric == "failures" else 0.0 if metric == "latency_ms" else {} if metric in {"recall_at_k", "stale_at_rank"} else 0.0) for metric in OFFICIAL_STALE_RANKING_METRICS},
                    }
            case["cells"] = cells
    except Exception as exc:
        semantic_reason = f"isolated semantic-memory MCP/core path unavailable: {exc}; no semantic-memory result was simulated"
        for case in projected:
            cells = case.get("cells", _baseline_stale_cells(case))
            cells["semantic_memory"] = {
                "status": "not_tested",
                "reason": semantic_reason,
                "evidence_packet": {},
                "selected_state": None,
                "disposition": "request_evidence",
                "metrics": {metric: ([] if metric == "failures" else 0.0 if metric == "latency_ms" else False) for metric in OFFICIAL_STALE_METRICS},
            }
            case["cells"] = cells
            if ranking:
                case["ranking"] = {
                    "status": "not_tested",
                    "reason": semantic_reason,
                    "ordered_candidate_ids": {},
                    "candidate_taxonomy": list(OFFICIAL_STALE_RANKING_CANDIDATE_KINDS),
                    "metrics": {metric: ([] if metric == "failures" else 0.0 if metric == "latency_ms" else {} if metric in {"recall_at_k", "stale_at_rank"} else 0.0) for metric in OFFICIAL_STALE_RANKING_METRICS},
                }
    finally:
        if client is not None:
            client.close()
        if temp_dir is not None:
            temp_dir.cleanup()
    split_counts = {
        "calibration": sum(case["split"] == "calibration" for case in projected),
        "heldout": sum(case["split"] == "heldout" for case in projected),
    }
    semantic_measured = sum(case["cells"]["semantic_memory"]["status"] in {"measured", "failed"} for case in projected)
    failures = [
        {"case_id": case["case_id"], "cell": cell, "failures": value["metrics"]["failures"]}
        for case in projected
        for cell, value in case["cells"].items()
        if value["metrics"]["failures"]
    ]
    receipt = {
        "adapter": "stale_official",
        "status": "measured",
        "source": source,
        "rows_evaluated": len(projected),
        "split_counts": split_counts,
        "split_policy": {"calibration": [0, 99], "heldout": [100, 399]},
        "tuning": {"calibration_only": True, "heldout_tuning": False, "learned_parameters": 0},
        "event_stream": {"kind": "ordered_session_digest_projection", "sessions_per_row": 50, "material_events_per_row": 2},
        "predeclared_metrics": list(OFFICIAL_STALE_METRICS),
        "baseline_definitions": {
            "semantic_memory": "actual isolated semantic-memory MCP/core add, supersede, witnessed-current, and historical-as-of path using the existing MCP client",
            "mutable_latest": "deterministic last-write-wins state retaining only M_new; no historical reconstruction",
            "append_only": "deterministic M_old plus M_new retention with unresolved-conflict abstention",
            "no_memory": "empty evidence packet and request-evidence disposition",
            "full_context_oracle": "deterministic oracle over all 50 ordered session digests and labeled M_old/M_new transition",
        },
        "aggregate_metrics": _aggregate_stale_metrics(projected),
        "model_grading": {"status": "not_tested", "reason": OFFICIAL_STALE_MODEL_GRADING_BLOCKER},
        "competitors": {"status": "not_tested", "reason": "no named competitor adapter was run on these identical rows"},
        "execution": {
            "llm_calls": 0,
            "judge_calls": 0,
            "network_dataset_downloads": 0,
            "active_services_modified": False,
            "isolated_local_server": launch_local,
            "semantic_memory_rows_measured": semantic_measured,
            "semantic_memory_endpoint": endpoint,
            "mcp_tools": tool_names,
        },
        "costs": {"estimated_usd": 0.0, "llm_tokens": 0, "rows": len(projected), "probes_per_row": 3},
        "failures": failures,
        "not_tested": [{"metric": "official_model_grading", "reason": OFFICIAL_STALE_MODEL_GRADING_BLOCKER}],
    }
    if ranking:
        receipt["ranking"] = {
            "status": "measured" if any(case["ranking"]["status"] in {"measured", "failed"} for case in projected) else "not_tested",
            "predeclared_metrics": list(OFFICIAL_STALE_RANKING_METRICS),
            "candidate_taxonomy": list(OFFICIAL_STALE_RANKING_CANDIDATE_KINDS),
            "policy": projected[0]["ranking_policy"] if projected else {},
            "aggregate_metrics": aggregate_ranking_metrics(projected),
            "claim_boundary": "retrieval ranking is measured separately from the existing semantic-memory state-integrity cell; no model responses or judges were run",
        }
    if semantic_measured != len(projected):
        receipt["not_tested"].append({"cell": "semantic_memory", "reason": semantic_reason})
    return receipt, projected


def write_official_stale_cases(path: Path, cases: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, sort_keys=True, separators=(",", ":")) + "\n")
    return sha256_path(path)


def render_official_stale_markdown(report: dict[str, Any], command: str, cases_path: Path) -> str:
    stale = report["official_stale"]
    grading = stale["model_grading"]
    calls_line = (
        f"- Target calls: `{grading['execution']['calls']['target']}`; judge calls: `{grading['execution']['calls']['judge']}`; retries: `{grading['execution']['retries']}`; failures: `{grading['execution']['failures']}`"
        if isinstance(grading.get("execution"), dict) and isinstance(grading["execution"].get("calls"), dict)
        else "- LLM calls: `0`; judge calls: `0`"
    )
    lines = [
        "# Official STALE Deterministic Adapter",
        "",
        f"- Dataset: `{stale['source']['path']}` (not copied into tracked files)",
        f"- SHA-256: `{stale['source']['sha256']}`",
        f"- Official repository commit: `{stale['source']['repository_commit']}`",
        f"- License: `{stale['source']['license']}`",
        f"- Rows: `{stale['rows_evaluated']}`; calibration `{stale['split_counts']['calibration']}`, held-out `{stale['split_counts']['heldout']}`",
        f"- Per-case sidecar: `{cases_path}` (`{report['raw_predictions']['official_stale']['sha256']}`)",
        calls_line,
        "",
        "## Predeclared metrics",
        "",
    ]
    lines.extend(f"- `{metric}`" for metric in stale["predeclared_metrics"])
    lines.extend(["", "## Baseline definitions", ""])
    lines.extend(f"- `{cell}` — {definition}" for cell, definition in stale["baseline_definitions"].items())
    lines.extend(["", "## Aggregate results", "", "| Cell | Current | Stale suppression | Conflict | False-premise proxy | Action-safe packet | History | Abstain/evidence | Mean latency ms | Failures |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for cell, value in stale["aggregate_metrics"].items():
        metrics = value["metrics"]
        def rate(name: str) -> str:
            result = metrics[name]["rate"]
            return "not tested" if result is None else f"{result:.3f}"
        latency = metrics["latency_ms"]["mean"]
        lines.append(f"| `{cell}` | {rate('current_state_selection')} | {rate('stale_suppression')} | {rate('conflict_preservation')} | {rate('false_premise_resistance_proxy')} | {rate('action_safe_evidence_packet')} | {rate('historical_reconstruction')} | {rate('abstain_request_evidence_correctness')} | {latency if latency is not None else 'not tested'} | {metrics['failures']['count']} |")
    if "ranking" in stale:
        ranking = stale["ranking"]
        metrics = ranking["aggregate_metrics"]["ranking"]["metrics"]
        lines.extend([
            "",
            "## Multi-candidate retrieval ranking (separate from state integrity)",
            "",
            f"- Candidate kinds: {', '.join('`' + kind + '`' for kind in ranking['candidate_taxonomy'])}",
            "- State integrity remains in the `semantic_memory` cell above; this lane retrieves six ordinary candidates and never infers a state transition from their ordering.",
            "",
            "| Recall@1 | Recall@3 | Recall@5 | MRR | nDCG | Current before stale | Safe evidence | Mean latency ms | Failures |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| {metrics['recall_at_k']['1']['rate'] if metrics['recall_at_k']['1']['rate'] is not None else 'not tested'} | {metrics['recall_at_k']['3']['rate'] if metrics['recall_at_k']['3']['rate'] is not None else 'not tested'} | {metrics['recall_at_k']['5']['rate'] if metrics['recall_at_k']['5']['rate'] is not None else 'not tested'} | {metrics['mrr']['mean'] if metrics['mrr']['mean'] is not None else 'not tested'} | {metrics['ndcg']['mean'] if metrics['ndcg']['mean'] is not None else 'not tested'} | {metrics['current_vs_stale_ordering']['rate'] if metrics['current_vs_stale_ordering']['rate'] is not None else 'not tested'} | {metrics['safe_evidence_rate']['rate'] if metrics['safe_evidence_rate']['rate'] is not None else 'not tested'} | {metrics['latency_ms']['mean'] if metrics['latency_ms']['mean'] is not None else 'not tested'} | {metrics['failures']['count']} |",
        ])
    lines.extend([
        "",
        "## Model grading",
        "",
        (
            f"Measured with target `{grading['models']['target_requested']}` and judge `{grading['models']['judge_requested']}` via `{grading['provider']}`. "
            f"Overall official-judge accuracy: `{grading['accuracy']['overall']}` ({grading['accuracy']['correct']}/{grading['accuracy']['total']}); "
            f"returned cost: `{grading['cost']['returned_usd']}` USD across `{grading['cost']['returned_cost_calls']}` calls; estimated cost: `{grading['cost']['estimated_usd']}` USD."
            if grading.get("status") == "measured" else f"`not_tested`: {grading['reason'].rstrip('.')}."
        ),
        "",
        "## Split and event-stream policy",
        "",
        "Rows 0–99 are calibration and rows 100–399 are held out. No parameters are learned and no held-out row is used for tuning. Each row retains all 50 ordered session positions as canonical JSON digests, while the two relevant state events retain their indices, timestamps, M_old, M_new, explanation, and all three probes.",
        "",
        "## Exact command",
        "",
        "```bash",
        command,
        "```",
        "",
        "## Claim boundary",
        "",
        (grading["claim_boundary"] if grading.get("claim_boundary") else "These are deterministic state/evidence measurements and proxies. They are not official response-accuracy scores and make no model-quality or competitor-superiority claim."),
        "",
    ])
    return "\n".join(lines)


def render_official_sleeper_markdown(report: dict[str, Any], command: str, cases_path: Path) -> str:
    sleeper = report["official_sleeper"]
    lines = [
        "# Official Sleeper Deterministic Admission / Action-Gate Adapter",
        "",
        f"- Official repository: `{sleeper['source']['root']}` at `{sleeper['source']['repository_commit']}`",
        f"- Rows: `{sleeper['rows_evaluated']}`; slices `{json.dumps(sleeper['slice_counts'], sort_keys=True)}`",
        f"- Per-case sidecar: `{cases_path}` (`{report['raw_predictions']['official_sleeper']['sha256']}`)",
        "- LLM calls: `0`; judge calls: `0`",
        f"- Upstream licensing caveat: {sleeper['source']['license_caveat']}",
        "",
        "## Exact upstream files",
        "",
        "| Slice | Source SHA-256 | Generated / evaluated split SHA-256 | Rows |",
        "|---|---|---|---:|",
    ]
    for dataset in sleeper["source"]["datasets"]:
        lines.append(f"| `{dataset['id']}` | `{dataset['source_sha256']}` | `{dataset['split_sha256']}` | {dataset['rows']} |")
    lines.extend(["", "## Predeclared baseline cells", ""])
    lines.extend(f"- `{cell}` — {definition}" for cell, definition in sleeper["baseline_definitions"].items())
    lines.extend(["", "## Aggregate deterministic results", "", "| Cell | Admission outcomes | Poison retrieval containment | Benign-save retention | Mean latency ms | Failures |", "|---|---|---:|---:|---:|---:|"])
    for cell, value in sleeper["aggregate_metrics"].items():
        metrics = value["metrics"]
        poison = metrics["poison_memory_retrieval_containment"]["rate"]
        benign = metrics["benign_save_retention"]["rate"]
        latency = metrics["latency_ms"]["mean"]
        lines.append(f"| `{cell}` | `{json.dumps(metrics['write_admission_outcome'], sort_keys=True)}` | {poison if poison is not None else 'not tested'} | {benign if benign is not None else 'not tested'} | {latency if latency is not None else 'not tested'} | {metrics['failures']['count']} |")
    lines.extend([
        "",
        "## Authority and metric boundaries",
        "",
        "- The governed cell calls the actual isolated MCP `sm_add_fact` admission gate and `sm_search_witnessed`; official source text is represented only by row/content digests in artifacts, not copied into this repository.",
        "- The MCP append contract frames evidence-backed sources as external evidence with denied assertion and action scopes. Purpose-specific governed assertion/action access and multi-principal decisions are not exposed by this MCP tool surface, so those containment metrics are `not_tested`, not inferred from a policy simulation.",
        f"- `{sleeper['model_grading']['status']}`: {sleeper['model_grading']['reason']}.",
        "- No response-quality, official paper score, competitor score, or model-quality claim is made.",
        "",
        "## Exact command",
        "",
        "```bash",
        command,
        "```",
        "",
    ])
    return "\n".join(lines)


def render_competitor_markdown(report: dict[str, Any], command: str) -> str:
    lines = [
        "# Named Competitor Deterministic Adapters",
        "",
        "All measured rows use the pinned official STALE M_old → M_new sequence and the same three probes. Sleeper is evaluated only for a native write-admission/governance claim.",
        "",
        "## Results",
        "",
        "| Competitor | Pin | STALE rows | Current | Stale suppression | Conflict | History | Mean latency ms | Sleeper |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for competitor_id in COMPETITOR_IDS:
        competitor = report["competitors"][competitor_id]
        stale = competitor["benchmarks"]["stale"]
        sleeper = competitor["benchmarks"]["sleeper"]
        pin = competitor["upstream"]
        if stale["status"] in {"measured", "failed"}:
            metrics = stale["aggregate_metrics"]["metrics"]
            lines.append(
                f"| `{competitor_id}` | `{pin['version']}` / `{pin['commit'][:12]}` | {stale['rows_evaluated']} | "
                f"{metrics['current_state_selection']['rate']:.3f} | {metrics['stale_suppression']['rate']:.3f} | "
                f"{metrics['conflict_preservation']['rate']:.3f} | {metrics['historical_reconstruction']['rate']:.3f} | "
                f"{metrics['latency_ms']['mean']} | `{sleeper['status']}` |"
            )
        else:
            lines.append(f"| `{competitor_id}` | `{pin['version']}` / `{pin['commit'][:12]}` | not tested | — | — | — | — | — | `{sleeper['status']}` |")
    lines.extend(["", "## Blockers and boundaries", ""])
    if any("ranking" in report["competitors"][competitor_id]["benchmarks"]["stale"] for competitor_id in COMPETITOR_IDS):
        lines.extend([
            "", "## Multi-candidate ranking (separate from state integrity)", "",
            "| Competitor | Rows | Recall@1 | Recall@3 | MRR | nDCG | Current before stale | Safe evidence |", "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for competitor_id in COMPETITOR_IDS:
            ranking = report["competitors"][competitor_id]["benchmarks"]["stale"].get("ranking")
            if not ranking or ranking["status"] not in {"measured", "failed"}:
                lines.append(f"| `{competitor_id}` | not tested | — | — | — | — | — | — |")
                continue
            metrics = ranking["aggregate_metrics"]["metrics"]
            lines.append(f"| `{competitor_id}` | {ranking['rows_evaluated']} | {metrics['recall_at_k']['1']['rate']} | {metrics['recall_at_k']['3']['rate']} | {metrics['mrr']['mean']} | {metrics['ndcg']['mean']} | {metrics['current_vs_stale_ordering']['rate']} | {metrics['safe_evidence_rate']['rate']} |")
    for competitor_id in COMPETITOR_IDS:
        competitor = report["competitors"][competitor_id]
        if competitor["benchmarks"]["stale"]["status"] == "not_tested":
            lines.append(f"- `{competitor_id}` — {competitor['benchmarks']['stale']['reason']}")
    lines.extend([
        "",
        "- Mem0 history is a native update-event log, not bitemporal as-of search.",
        "- Letta's pinned legacy V1 server is maintenance-mode. Its embedding-optional passage API documents insert/list/search/delete but no passage update or history path; those capabilities are unavailable and are not adapter-emulated.",
        "- Letta agent creation structurally requires an LLM model handle, but direct passage operations do not invoke that model.",
        "- LangMem native keyed update overwrites the old item; history/conflict preservation are unavailable, not adapter-emulated.",
        "- Each case uses an isolated namespace containing one keyed current memory after native update. The probes therefore measure update/search visibility and state semantics, not multi-candidate retrieval ranking.",
        "- Both measured adapters receive the same fixed SHA-256-derived 16-dimensional local embedding through their supported public embedding interfaces; no embedding provider call is made.",
        "- `not_supported` Sleeper cells are not failures. None of the measured competitors documents a write-admission/governance gate on these public APIs.",
        "- These are deterministic state/evidence proxies, not official model-graded response scores or a general superiority claim.",
        "",
        "## Exact command",
        "",
        "```bash",
        command,
        "```",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local deterministic adapters for diagnostic memory benchmarks.")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "shared/fixtures/diagnostic-memory-fixtures.json")
    parser.add_argument("--adapter-fixture", action="append", default=[], metavar="ADAPTER_ID=PATH", help="Use an independently obtained local adapter fixture; never downloads data.")
    parser.add_argument("--memory-influence-fixtures", type=Path, default=ROOT / "shared/fixtures/memory-influence-fixtures.json", help="CC0 local causal-influence fixture bundle embedded in this diagnostic receipt.")
    parser.add_argument("--memory-influence-mode", choices=("offline", "risk_triggered"), default="offline", help="Run every deterministic case offline, or only risk-triggered cases.")
    parser.add_argument("--official-stale-dataset", type=Path, help="Run the pinned official STALE adapter against the local 400-row source file.")
    parser.add_argument("--official-stale-limit", type=int, help="Prefix row limit for smoke testing only; full runs omit this flag.")
    parser.add_argument("--official-stale-ranking", action="store_true", help="Add the deterministic six-candidate ranking lane while retaining separate state-integrity cells.")
    parser.add_argument("--official-stale-cases-out", type=Path, help="Per-case JSONL sidecar for the official STALE adapter.")
    parser.add_argument("--official-stale-launch-local", action="store_true", help="Exercise an isolated temporary semantic-memory MCP/core server; never modifies an active service.")
    parser.add_argument("--official-stale-model-grade", action="store_true", help="Run pinned official STALE target and judge prompts over existing semantic-memory retrieval receipts.")
    parser.add_argument("--official-stale-retrieval-receipts", type=Path, help="Existing official 400-case semantic-memory per-case JSONL receipt.")
    parser.add_argument("--official-stale-evaluator-root", type=Path, default=Path("/tmp/stale-official"), help="Pinned official STALE evaluator checkout.")
    parser.add_argument("--official-stale-model-output-dir", type=Path, help="Local raw provider responses and model-graded per-case artifacts.")
    parser.add_argument("--official-stale-target-model", default=OFFICIAL_STALE_TARGET_MODEL)
    parser.add_argument("--official-stale-judge-model", default=OFFICIAL_STALE_JUDGE_MODEL)
    parser.add_argument("--official-stale-model-concurrency", type=int, default=10)
    parser.add_argument("--official-stale-max-spend-usd", type=float, default=OFFICIAL_STALE_MODEL_MAX_SPEND_USD)
    parser.add_argument("--official-sleeper-root", type=Path, help="Pinned local Sleeper checkout; released datasets are read in place and never copied.")
    parser.add_argument("--official-sleeper-limit-per-slice", type=int, help="Bound each Sleeper slice for smoke testing; full runs omit this flag.")
    parser.add_argument("--official-sleeper-cases-out", type=Path, help="Per-case JSONL sidecar for the official Sleeper adapter.")
    parser.add_argument("--official-sleeper-launch-local", action="store_true", help="Exercise an isolated temporary semantic-memory MCP server; never modifies an active service.")
    parser.add_argument("--markdown-out", type=Path, help="Markdown report for an official STALE run.")
    parser.add_argument("--competitor-python", action="append", default=[], metavar="COMPETITOR_ID=PATH", help="Run a named adapter in an isolated competitor venv interpreter.")
    parser.add_argument("--competitor-all-stale", action="store_true", help="Promote competitor execution from the predeclared 20-row smoke to all 400 rows after the smoke met its bound.")
    parser.add_argument("--competitor-cases-dir", type=Path, help="Directory for hashed per-competitor STALE JSONL sidecars.")
    parser.add_argument("--competitor-locks-dir", type=Path, help="Directory containing COMPETITOR_ID.lock.txt environment locks to hash into receipts.")
    parser.add_argument("--competitor-report-out", type=Path, help="Markdown report for named competitor results and blockers.")
    parser.add_argument("--competitor-blockers", type=Path, help="JSON blocker receipt for candidates that could not be measured.")
    parser.add_argument("--competitor-worker", choices=COMPETITOR_IDS, help=argparse.SUPPRESS)
    parser.add_argument("--competitor-worker-ranking", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--competitor-worker-input", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--competitor-worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.competitor_worker:
        if not args.competitor_worker_input or not args.competitor_worker_output:
            parser.error("competitor worker requires input and output paths")
        try:
            return run_competitor_worker(args.competitor_worker, args.competitor_worker_input, args.competitor_worker_output, ranking=args.competitor_worker_ranking)
        except Exception as exc:
            parser.error(f"competitor worker failed: {type(exc).__name__}: {exc}")
    if args.out is None:
        parser.error("--out is required")
    try:
        load_fixture_bundle(args.fixtures)
        paths = parse_adapter_paths(args.adapter_fixture)
        competitor_paths = parse_competitor_paths(args.competitor_python)
        competitor_blockers = load_competitor_blockers(args.competitor_blockers)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    report = build_diagnostic_report(
        args.fixtures,
        adapter_paths=paths,
        memory_influence_fixtures=args.memory_influence_fixtures,
        memory_influence_mode=args.memory_influence_mode,
    )
    if args.official_stale_dataset and args.official_sleeper_root:
        parser.error("run one official adapter per invocation so its markdown and sidecar remain unambiguous")
    if args.official_stale_dataset:
        competitor_only_output = bool(competitor_paths or competitor_blockers)
        if (not args.official_stale_cases_out or not args.markdown_out) and not competitor_only_output:
            parser.error("--official-stale-dataset requires --official-stale-cases-out and --markdown-out unless named competitor output is requested")
        try:
            stale_receipt, stale_cases = run_official_stale_adapter(
                args.official_stale_dataset,
                limit=args.official_stale_limit,
                launch_local=args.official_stale_launch_local,
                ranking=args.official_stale_ranking,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        if args.official_stale_model_grade:
            if not args.official_stale_retrieval_receipts or not args.official_stale_model_output_dir:
                parser.error("--official-stale-model-grade requires --official-stale-retrieval-receipts and --official-stale-model-output-dir")
            try:
                model_grade, _ = run_official_stale_model_grading(
                    args.official_stale_dataset,
                    args.official_stale_retrieval_receipts,
                    args.official_stale_evaluator_root,
                    args.official_stale_model_output_dir,
                    concurrency=args.official_stale_model_concurrency,
                    max_spend_usd=args.official_stale_max_spend_usd,
                    target_model=args.official_stale_target_model,
                    judge_model=args.official_stale_judge_model,
                )
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                parser.error(str(exc))
            stale_receipt["model_grading"] = model_grade
            stale_receipt["execution"].update({
                "llm_calls": model_grade["execution"]["calls"]["target"],
                "judge_calls": model_grade["execution"]["calls"]["judge"],
                "provider_attempts": model_grade["execution"]["attempts"],
                "provider_retries": model_grade["execution"]["retries"],
                "provider_failures": model_grade["execution"]["failures"],
            })
            stale_receipt["costs"] = model_grade["cost"]
            if model_grade["status"] == "measured":
                stale_receipt["not_tested"] = [item for item in stale_receipt["not_tested"] if item.get("metric") != "official_model_grading"]
            else:
                for item in stale_receipt["not_tested"]:
                    if item.get("metric") == "official_model_grading":
                        item["reason"] = model_grade["reason"]
        report["official_stale"] = stale_receipt
        report["input_hashes"]["official_stale_dataset"] = stale_receipt["source"]["sha256"]
        if args.official_stale_cases_out:
            cases_hash = write_official_stale_cases(args.official_stale_cases_out, stale_cases)
            report["raw_predictions"]["official_stale"] = {"path": str(args.official_stale_cases_out), "rows": len(stale_cases), "sha256": cases_hash}
        report["costs"]["official_stale"] = stale_receipt["costs"]
        if args.official_stale_model_grade:
            report["input_hashes"]["official_stale_retrieval_receipts"] = model_grade["artifacts"]["retrieval_receipts"]["sha256"] if "retrieval_receipts" in model_grade["artifacts"] else sha256_path(args.official_stale_retrieval_receipts)
            for name, digest in model_grade["evaluator"]["files"].items():
                report["input_hashes"]["official_stale_evaluator_" + Path(name).name] = digest
            if "raw_provider_responses" in model_grade["artifacts"]:
                report["raw_predictions"]["official_stale_model_raw"] = model_grade["artifacts"]["raw_provider_responses"]
            if "per_case" in model_grade["artifacts"]:
                report["raw_predictions"]["official_stale_model_graded"] = model_grade["artifacts"]["per_case"]
        report["failures"].extend({"adapter": "stale_official", **failure} for failure in stale_receipt["failures"])
        report["not_tested"].extend({"adapter": "stale_official", **item} for item in stale_receipt["not_tested"])
        if competitor_paths or competitor_blockers:
            if not args.competitor_cases_dir or not args.competitor_report_out:
                parser.error("competitor execution/blockers require --competitor-cases-dir and --competitor-report-out")
            selected_cases = select_competitor_stale_cases(stale_cases, all_rows=args.competitor_all_stale)
            state_cases = [{key: value for key, value in case.items() if key not in {"ranking_candidates", "ranking_policy", "ranking", "cells"}} for case in selected_cases]
            for competitor_id in COMPETITOR_IDS:
                python_path = competitor_paths.get(competitor_id)
                if python_path is not None:
                    if not python_path.is_file():
                        record = _unmeasured_competitor(competitor_id, f"isolated competitor interpreter is absent: {python_path}")
                    else:
                        competitor_cases = args.competitor_cases_dir / f"stale-{competitor_id}-per-case.jsonl"
                        record = run_competitor_stale_subprocess(competitor_id, python_path, state_cases, competitor_cases, all_rows=args.competitor_all_stale)
                        stale_result = record["benchmarks"]["stale"]
                        if stale_result["status"] in {"measured", "failed"}:
                            report["raw_predictions"][f"competitor_{competitor_id}_stale"] = stale_result["per_case"]
                            report["costs"][f"competitor_{competitor_id}_stale"] = {
                                "estimated_usd": 0.0, "llm_tokens": 0, "rows": stale_result["rows_evaluated"], "probes_per_row": 3,
                            }
                        if args.official_stale_ranking and stale_result["status"] in {"measured", "failed"}:
                            ranking_cases = args.competitor_cases_dir / f"stale-{competitor_id}-ranking-per-case.jsonl"
                            ranking_record = run_competitor_stale_subprocess(competitor_id, python_path, selected_cases, ranking_cases, all_rows=args.competitor_all_stale, ranking=True)
                            ranking_result = ranking_record["benchmarks"]["stale"]
                            stale_result["ranking"] = ranking_result
                            if ranking_result["status"] in {"measured", "failed"}:
                                report["raw_predictions"][f"competitor_{competitor_id}_ranking"] = ranking_result["per_case"]
                                report["costs"][f"competitor_{competitor_id}_ranking"] = {
                                    "estimated_usd": 0.0, "llm_tokens": 0, "rows": ranking_result["rows_evaluated"], "probes_per_row": 3,
                                }
                elif competitor_id in competitor_blockers:
                    blocker = competitor_blockers[competitor_id]
                    record = _unmeasured_competitor(competitor_id, str(blocker["reason"]))
                    record["blocker_receipt"] = blocker
                else:
                    record = report["competitors"][competitor_id]
                if args.competitor_locks_dir:
                    lock_path = args.competitor_locks_dir / f"{competitor_id}.lock.txt"
                    if lock_path.is_file():
                        record["environment_lock"] = {"path": str(lock_path), "sha256": sha256_path(lock_path)}
                report["competitors"][competitor_id] = record
                if record["status"] == "not_tested":
                    report["not_tested"].append({"competitor": competitor_id, "benchmark": "stale", "reason": record["benchmarks"]["stale"]["reason"]})
                report["not_tested"].append({"competitor": competitor_id, "benchmark": "sleeper", "status": "not_supported", "reason": record["benchmarks"]["sleeper"]["reason"]})
            stale_receipt["competitors"] = {competitor_id: report["competitors"][competitor_id]["benchmarks"]["stale"]["status"] for competitor_id in COMPETITOR_IDS}
            if args.competitor_blockers:
                report["input_hashes"]["competitor_blockers"] = sha256_path(args.competitor_blockers)
    if args.official_sleeper_root:
        if not args.official_sleeper_cases_out or not args.markdown_out:
            parser.error("--official-sleeper-root requires --official-sleeper-cases-out and --markdown-out")
        try:
            sleeper_receipt, sleeper_cases = run_official_sleeper_adapter(
                args.official_sleeper_root,
                limit_per_slice=args.official_sleeper_limit_per_slice,
                launch_local=args.official_sleeper_launch_local,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        report["official_sleeper"] = sleeper_receipt
        cases_hash = write_official_stale_cases(args.official_sleeper_cases_out, sleeper_cases)
        report["input_hashes"].update({f"official_sleeper_{item['id']}_source": item["source_sha256"] for item in sleeper_receipt["source"]["datasets"]})
        report["input_hashes"].update({f"official_sleeper_{item['id']}_split": item["split_sha256"] for item in sleeper_receipt["source"]["datasets"]})
        report["raw_predictions"]["official_sleeper"] = {"path": str(args.official_sleeper_cases_out), "rows": len(sleeper_cases), "sha256": cases_hash}
        report["costs"]["official_sleeper"] = sleeper_receipt["costs"]
        report["failures"].extend({"adapter": "sleeper_official", **failure} for failure in sleeper_receipt["failures"])
        report["not_tested"].extend({"adapter": "sleeper_official", **item} for item in sleeper_receipt["not_tested"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.official_stale_dataset and args.markdown_out and args.official_stale_cases_out:
        command = " ".join(["python3", str(Path(__file__).relative_to(ROOT)), *sys.argv[1:]])
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_official_stale_markdown(report, command, args.official_stale_cases_out), encoding="utf-8")
    if args.official_sleeper_root and args.markdown_out and args.official_sleeper_cases_out:
        command = " ".join(["python3", str(Path(__file__).relative_to(ROOT)), *sys.argv[1:]])
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_official_sleeper_markdown(report, command, args.official_sleeper_cases_out), encoding="utf-8")
    if args.competitor_report_out and (competitor_paths or competitor_blockers):
        command = " ".join(["python3", str(Path(__file__).relative_to(ROOT)), *sys.argv[1:]])
        args.competitor_report_out.parent.mkdir(parents=True, exist_ok=True)
        args.competitor_report_out.write_text(render_competitor_markdown(report, command), encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "out": str(args.out), "statuses": {key: value["status"] for key, value in report["adapters"].items()}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
