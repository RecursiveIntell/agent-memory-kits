#!/usr/bin/env python3
"""Run LongMemEval generation or judging through an isolated Hermes one-shot store.

The prior /tmp runner inherited the desktop's HERMES_HOME and HERMES_DESKTOP
variables. Each `hermes -z` call consequently created a desktop-visible session.
This runner intentionally strips ambient HERMES_* state and gives every benchmark
invocation a repo-owned state root. It never touches the desktop session database.

Outputs are durable JSONL checkpoints. Re-running resumes only missing question
IDs; failures are retained separately and make the process exit non-zero.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LONGMEMEVAL = ROOT / "benchmarks" / "LongMemEval"
if str(LONGMEMEVAL) not in sys.path:
    sys.path.insert(0, str(LONGMEMEVAL))

from src.evaluation.evaluate_qa import get_anscheck_prompt
from src.generation.run_generation import prepare_prompt

try:
    import tiktoken
except ImportError as exc:  # pragma: no cover - exercised by preflight
    raise SystemExit("LongMemEval venv is required: benchmarks/LongMemEval/.venv") from exc

WRITE_LOCK = threading.Lock()


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        raw = handle.read().lstrip()
    if not raw:
        return []
    if raw.startswith("["):
        value = json.loads(raw)
        if not isinstance(value, list):
            raise ValueError(f"expected JSON array in {path}")
        return value
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        str(row["question_id"])
        for row in load_records(path)
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }


def validate_generation_input(rows: list[dict[str, Any],]) -> None:
    """Reject a prior hypothesis log before it can create a misleading error storm."""
    required = {
        "question_id",
        "question",
        "question_date",
        "haystack_dates",
        "haystack_session_ids",
        "haystack_sessions",
        "retrieval_results",
    }
    invalid: list[tuple[str, list[str]]] = []
    for row in rows:
        if not isinstance(row, dict):
            invalid.append(("<non-object>", sorted(required)))
            continue
        missing = sorted(required - set(row))
        ranked_items = row.get("retrieval_results", {}).get("ranked_items") if not missing else None
        if missing or not isinstance(ranked_items, list) or not ranked_items:
            if not missing and (not isinstance(ranked_items, list) or not ranked_items):
                missing.append("retrieval_results.ranked_items (non-empty list)")
            invalid.append((str(row.get("question_id", "<missing>")), missing))
    if invalid:
        examples = "; ".join(f"{qid}: {', '.join(missing)}" for qid, missing in invalid[:3])
        raise SystemExit(
            "generation input must be a LongMemEval retrieval log with canonical question fields; "
            f"invalid_records={len(invalid)}/{len(rows)}; examples: {examples}"
        )


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with WRITE_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(encoded + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def isolated_env(hermes_home: Path) -> dict[str, str]:
    """Return an environment that cannot inherit desktop Hermes state."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("HERMES_")}
    # Hermes injects its own venv path here; keeping it defeats LongMemEval's venv.
    env.pop("PYTHONPATH", None)
    env["HERMES_HOME"] = str(hermes_home)
    env["HERMES_BENCHMARK_ISOLATED"] = "1"
    return env


def ask(prompt: str, *, reasoning: str, hermes: str, hermes_home: Path, timeout_s: int) -> str:
    """Execute exactly one isolated Hermes one-shot request."""
    cmd = [
        hermes,
        "--cli",
        "--safe-mode",
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-luna",
        "--reasoning",
        reasoning,
        "--toolsets",
        "",
        "--oneshot",
        prompt,
    ]
    proc = subprocess.run(
        cmd,
        cwd=LONGMEMEVAL,
        env=isolated_env(hermes_home),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout or "Hermes invocation failed").strip()[-4000:]
        raise RuntimeError(f"Hermes exit={proc.returncode}: {detail}")
    answer = proc.stdout.strip()
    if not answer:
        raise RuntimeError("Hermes returned empty final response")
    return answer


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("generate", "judge"), required=True)
    p.add_argument("--in-file", type=Path, required=True)
    p.add_argument("--out-file", type=Path, required=True)
    p.add_argument("--reference-file", type=Path)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--reasoning", default="high")
    p.add_argument("--max-retrieval-tokens", type=int, default=20_000)
    p.add_argument("--limit", type=int, help="process at most this many currently missing IDs")
    p.add_argument("--timeout-seconds", type=int, default=600)
    p.add_argument("--hermes", default="hermes")
    p.add_argument(
        "--hermes-home",
        type=Path,
        # A named profile creates a separate state.db while Hermes' supported
        # profile fallback reads the root auth.json without copying OAuth tokens
        # into the repository or the benchmark state directory.
        default=Path.home() / ".hermes" / "profiles" / "longmemeval-bench",
        help="benchmark-only Hermes profile state root (never the desktop root)",
    )
    return p


def main() -> int:
    args = parser().parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    if args.mode == "judge" and args.reference_file is None:
        raise SystemExit("--reference-file is required for judge mode")

    in_file = args.in_file.resolve()
    out_file = args.out_file.resolve()
    hermes_home = args.hermes_home.resolve()
    desktop_home = (Path.home() / ".hermes").resolve()
    allowed_profile_home = desktop_home / "profiles" / "longmemeval-bench"
    if hermes_home == desktop_home or (
        desktop_home in hermes_home.parents and hermes_home != allowed_profile_home
    ):
        raise SystemExit(
            "refusing desktop-scoped --hermes-home; use the dedicated "
            "~/.hermes/profiles/longmemeval-bench profile or an external benchmark root"
        )
    if not in_file.is_file():
        raise SystemExit(f"input does not exist: {in_file}")

    hermes_home.mkdir(parents=True, exist_ok=True)
    rows = load_records(in_file)
    if args.mode == "generate":
        validate_generation_input(rows)
    done = completed_ids(out_file)
    todo = [row for row in rows if str(row.get("question_id")) not in done]
    if args.limit is not None:
        todo = todo[: args.limit]
    errors_file = out_file.with_suffix(out_file.suffix + ".errors.jsonl")
    print(
        json.dumps(
            {
                "mode": args.mode,
                "total": len(rows),
                "already_done": len(done),
                "todo": len(todo),
                "hermes_home": str(hermes_home),
                "desktop_home": str(desktop_home),
                "workers": args.workers,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    tokenizer = tiktoken.get_encoding("o200k_base")
    references = (
        {str(row["question_id"]): row for row in load_records(args.reference_file.resolve())}
        if args.mode == "judge"
        else {}
    )

    def work(row: dict[str, Any]) -> dict[str, Any]:
        qid = str(row["question_id"])
        if args.mode == "generate":
            prompt = prepare_prompt(
                row,
                "flat-session",
                20,
                False,
                "json",
                True,
                tokenizer,
                "openai",
                args.max_retrieval_tokens,
                "none",
            )
            answer = ask(
                prompt,
                reasoning=args.reasoning,
                hermes=args.hermes,
                hermes_home=hermes_home,
                timeout_s=args.timeout_seconds,
            )
            return {"question_id": qid, "hypothesis": answer}
        reference = references.get(qid)
        if reference is None:
            raise KeyError(f"missing reference question_id: {qid}")
        prompt = get_anscheck_prompt(
            reference["question_type"],
            reference["question"],
            reference["answer"],
            row["hypothesis"],
            abstention="_abs" in qid,
        )
        verdict = ask(
            prompt,
            reasoning=args.reasoning,
            hermes=args.hermes,
            hermes_home=hermes_home,
            timeout_s=args.timeout_seconds,
        )
        return {
            "question_id": qid,
            "hypothesis": row["hypothesis"],
            "autoeval_label": {"model": "gpt-5.6-luna", "label": "yes" in verdict.lower()},
            "judge_response": verdict,
        }

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(work, row): str(row["question_id"]) for row in todo}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            qid = futures[future]
            try:
                append_jsonl(out_file, future.result())
            except Exception as exc:  # preserve failure evidence and allow resume
                failures += 1
                append_jsonl(
                    errors_file,
                    {"question_id": qid, "error_type": type(exc).__name__, "message": str(exc)},
                )
            if index == 1 or index % 10 == 0 or index == len(todo):
                print(f"progress={index}/{len(todo)} failures={failures}", flush=True)

    if failures:
        raise SystemExit(f"incomplete: {failures} failures; rerun resumes only missing IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
