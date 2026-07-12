#!/usr/bin/env python3
"""Cross-engine compaction benchmark.

Feeds identical test transcripts to multiple context-compression engines
and measures compression ratio, time, and fallback availability.
Fails open: engines that aren't installed are marked unavailable and skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def approx_token_count(text: str) -> int:
    """Rough token estimate: chars / 4."""
    return max(1, len(text) // 4)


def messages_to_text(messages: list[dict[str, str]]) -> str:
    """Flatten messages into a single text blob for token counting."""
    return "\n".join(f"{m['role']}: {m['content']}" for m in messages)


def machine_fingerprint() -> str:
    raw = f"{platform.node()}|{platform.machine()}|{platform.python_version()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

def run_context_governor(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Call ~/.cargo/bin/context-governor compact with JSON stdin."""
    cg_bin = Path.home() / ".cargo" / "bin" / "context-governor"
    if not cg_bin.exists():
        return {"available": False, "compacted_messages": None}

    request = {
        "session_id": "cross-engine-benchmark",
        "messages": messages,
        "policy": {
            "target_tokens": 1200,
            "protect_first_n": 2,
            "protect_last_n": 2,
            "summary_max_chars": 2400,
            "allocator": "deterministic_v1",
            "semantic_memory_enabled": False,
            "archive_memory_enabled": False,
            "budget_mode": "hard_cascade",
            "token_counter": "approx_chars",
        },
    }
    try:
        proc = subprocess.run(
            [str(cg_bin), "compact"],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return {"available": False, "compacted_messages": None}
        resp = json.loads(proc.stdout)
        compacted = resp.get("messages", resp.get("compacted_messages", []))
        return {"available": True, "compacted_messages": compacted}
    except Exception:
        return {"available": False, "compacted_messages": None}


def run_head_tail(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Simple Python head-tail: keep first 2 + last 2, summarize rest."""
    if len(messages) <= 4:
        return {"available": True, "compacted_messages": messages}
    head = messages[:2]
    tail = messages[-2:]
    omitted = len(messages) - 4
    summary_msg = {
        "role": "system",
        "content": f"[{omitted} messages omitted]",
    }
    return {"available": True, "compacted_messages": head + [summary_msg] + tail}


def run_squeez(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Call `squeez` CLI if available."""
    if shutil.which("squeez") is None:
        return {"available": False, "compacted_messages": None}
    request = {"messages": messages}
    try:
        proc = subprocess.run(
            ["squeez"],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return {"available": False, "compacted_messages": None}
        resp = json.loads(proc.stdout)
        compacted = resp.get("messages", [])
        return {"available": True, "compacted_messages": compacted}
    except Exception:
        return {"available": False, "compacted_messages": None}


ENGINES = {
    "context-governor": run_context_governor,
    "head-tail": run_head_tail,
    "squeez": run_squeez,
}


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def benchmark_engine(
    engine_name: str,
    engine_fn,
    fixtures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run one engine against all fixtures, return aggregate metrics."""
    available = True
    total_before = 0
    total_after = 0
    total_time = 0.0
    exact_fallback_status = "unavailable"
    exact_fallback_verified = False
    per_fixture: list[dict[str, Any]] = []

    for fixture in fixtures:
        messages = fixture["messages"]
        before_text = messages_to_text(messages)
        token_before = approx_token_count(before_text)

        t0 = time.monotonic()
        result = engine_fn(messages)
        elapsed = time.monotonic() - t0

        if not result["available"]:
            available = False
            per_fixture.append({
                "name": fixture.get("name", "unnamed"),
                "available": False,
            })
            continue

        compacted = result["compacted_messages"]
        after_text = messages_to_text(compacted) if compacted else ""
        token_after = approx_token_count(after_text)

        total_before += token_before
        total_after += token_after
        total_time += elapsed

        per_fixture.append({
            "name": fixture.get("name", "unnamed"),
            "token_before": token_before,
            "token_after": token_after,
            "time_secs": round(elapsed, 6),
        })

    compression_ratio = 0.0
    if total_before > 0 and total_after > 0:
        compression_ratio = round(total_after / total_before, 4)

    # A marker that N messages were omitted is not exact fallback. The current
    # adapter also does not exercise context-governor's store + expand API, so
    # this benchmark must not award durable recovery credit to any engine.
    if engine_name == "context-governor" and available:
        exact_fallback_status = "not_verified"

    status = "tested" if available else "unsupported"

    return {
        "available": available,
        "status": status,
        "compression_ratio": compression_ratio,
        "time_secs": round(total_time, 6),
        "exact_fallback_status": exact_fallback_status,
        "exact_fallback_verified": exact_fallback_verified,
        "approx_tokens_before": total_before if available else 0,
        "approx_tokens_after": total_after if available else 0,
        "per_fixture": per_fixture,
    }


def load_fixtures(fixtures_dir: Path) -> list[dict[str, Any]]:
    """Load compaction-test.json from fixtures dir."""
    fixture_file = fixtures_dir / "compaction-test.json"
    if not fixture_file.exists():
        # Generate default fixtures
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        default = generate_default_fixtures()
        fixture_file.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(fixture_file.read_text())


def generate_default_fixtures() -> list[dict[str, Any]]:
    """Generate 3 test transcripts with 5-10 messages each, 200-500 chars per message."""
    def make_conversation(name: str, n_msgs: int) -> dict[str, Any]:
        messages = []
        topics = [
            "database query optimization",
            "API endpoint design",
            "user authentication flow",
            "error handling strategy",
            "code review feedback",
            "deployment pipeline setup",
            "performance profiling results",
            "data migration plan",
            "testing coverage analysis",
            "architecture decision record",
        ]
        for i in range(n_msgs):
            role = "user" if i % 2 == 0 else "assistant"
            topic = topics[i % len(topics)]
            # Pad content to be 200-500 chars
            content = (
                f"Regarding {topic}: this is message number {i + 1} in the {name} transcript. "
                f"We need to discuss the implications and trade-offs carefully before proceeding "
                f"with any changes to the current implementation. "
                f"The key considerations include performance impact, maintainability, and "
                f"alignment with our overall architectural goals for the project."
            )
            # Ensure within 200-500 range
            if len(content) < 200:
                content = content + " " + "x" * (200 - len(content))
            elif len(content) > 500:
                content = content[:500]
            messages.append({"role": role, "content": content})
        return {"name": name, "messages": messages}

    return [
        make_conversation("short-chat", 5),
        make_conversation("medium-chat", 7),
        make_conversation("long-chat", 10),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cross-engine compaction benchmark"
    )
    parser.add_argument(
        "--fixtures-dir",
        default=None,
        help="Directory containing compaction-test.json (default: shared/fixtures/)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output JSON file path",
    )

    args = parser.parse_args()

    # Resolve fixtures dir relative to the script location
    script_dir = Path(__file__).resolve().parent.parent  # shared/
    if args.fixtures_dir:
        fixtures_dir = Path(args.fixtures_dir)
    else:
        fixtures_dir = script_dir / "fixtures"

    fixtures = load_fixtures(fixtures_dir)

    engines_report: dict[str, Any] = {}
    all_per_fixture: list[dict[str, Any]] = []

    for engine_name, engine_fn in ENGINES.items():
        report = benchmark_engine(engine_name, engine_fn, fixtures)
        engines_report[engine_name] = report

    # Build per_fixture summary across engines
    for fixture in fixtures:
        entry = {"name": fixture.get("name", "unnamed")}
        for engine_name in ENGINES:
            eng_report = engines_report[engine_name]
            for pf in eng_report.get("per_fixture", []):
                if pf["name"] == entry["name"]:
                    entry[engine_name] = {
                        "token_before": pf.get("token_before", 0),
                        "token_after": pf.get("token_after", 0),
                        "available": pf.get("available", eng_report["available"]),
                    }
                    break
        all_per_fixture.append(entry)

    # Remove per_fixture from engine entries (it's redundant with top-level)
    for engine_name in ENGINES:
        engines_report[engine_name].pop("per_fixture", None)

    bench_report = {
        "schema": "CompactionBenchmarkV2",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine_fingerprint": machine_fingerprint(),
        "token_counter": "approx_chars_floor_v1",
        "claim_boundary": "local mechanics only; no model answerability or cross-engine superiority claim",
        "engines": engines_report,
        "per_fixture": all_per_fixture,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bench_report, indent=2))
    print(f"Benchmark report written to {out_path}")
    for engine_name, report in engines_report.items():
        status = "available" if report["available"] else "NOT available (skipped)"
        print(f"  {engine_name}: {status}, ratio={report['compression_ratio']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())