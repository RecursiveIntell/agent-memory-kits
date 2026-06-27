#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = ROOT / "hooks"
DEFAULT_CASES = [
    {
        "name": "plugin install",
        "query": "semantic-memory Codex plugin global hooks setup doctor",
        "expected": ["semantic-memory", "hook"],
    },
    {
        "name": "codebase ingestion",
        "query": "ingest repository into semantic memory with dedupe namespace code repo",
        "expected": ["ingest", "code"],
    },
    {
        "name": "new direct read tools",
        "query": "semantic-memory MCP list facts get fact neighbors conversation sessions",
        "expected": ["semantic-memory", "tools"],
    },
    {
        "name": "supersession workflow",
        "query": "semantic-memory stale fact supersession sm_supersede_fact",
        "expected": ["supersede", "stale"],
    },
]
HOOK_CASES = [
    {
        "name": "codex optimization prompt avoids generic agent crates",
        "prompt": "examine and research everything to make this perform as well as possible for codex, a coding agent.",
        "should_inject": True,
        "must_include": ["codex", "semantic-memory plugin"],
        "must_not_include": ["agent-graph", "aidens-testkit"],
    },
    {
        "name": "generic restart prompt stays quiet",
        "prompt": "i have restarted everything. How does everything seem to look and function?",
        "should_inject": False,
        "must_not_include": ["continuity-runtime", "receipt-bench", "aidens-testkit"],
    },
]


def rpc_call(tool: str, arguments: dict, timeout: int = 20) -> dict | None:
    wrapper = ROOT / "scripts/run-server.sh"
    reqs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "semantic-memory-eval", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": arguments}},
    ]
    proc = subprocess.run(
        [str(wrapper)],
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


def load_cases(path: Path | None) -> list[dict]:
    if not path:
        return DEFAULT_CASES
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("cases", [])
    if isinstance(data, list):
        return data
    raise ValueError("cases file must be a JSON list or an object with a cases list")


def gated_hits(results: list[dict]) -> list[dict]:
    score_key = "cosine_similarity" if any(hit.get("cosine_similarity") is not None for hit in results) else "score"
    hits = sorted(results, key=lambda item: float(item.get(score_key) or 0), reverse=True)
    if not hits:
        return []
    mintop = float(os.environ.get("SM_RECALL_MINTOP", "0.58"))
    band = float(os.environ.get("SM_RECALL_BAND", "0.12"))
    absfloor = float(os.environ.get("SM_RECALL_ABSFLOOR", "0.54"))
    scorerel = float(os.environ.get("SM_RECALL_SCOREREL", "0.5"))
    max_hits = int(os.environ.get("SM_RECALL_MAXHITS", "4"))
    top = float(hits[0].get(score_key) or 0)
    if score_key == "cosine_similarity":
        if top < mintop:
            return []
        floor = max(absfloor, top - band)
        return [hit for hit in hits if float(hit.get(score_key) or 0) >= floor][:max_hits]
    if top <= 0:
        return []
    return [hit for hit in hits if float(hit.get(score_key) or 0) >= top * scorerel][:max_hits]


def run_hook(prompt: str, timeout: int = 20) -> str:
    proc = subprocess.run(
        [str(HOOK_DIR / "memory-recall.py")],
        input=json.dumps({"prompt": prompt}) + "\n",
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "SM_AUTO_INGEST": "0"},
    )
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate semantic-memory recall and hook gating.")
    parser.add_argument("--cases", type=Path, help="JSON list of cases: name, query, expected string list")
    parser.add_argument("--top-k", type=int, default=int(os.environ.get("SM_RECALL_TOPK", "6")))
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    output = []
    hook_output = []
    failures = 0
    smoke = []
    namespaces = rpc_call("sm_list_namespaces", {})
    if not namespaces or not namespaces.get("ok"):
        if args.json:
            print(json.dumps({"ok": False, "error": "sm_list_namespaces smoke failed"}, indent=2))
        else:
            print("FAIL sm_list_namespaces smoke")
        return 1
    else:
        smoke.append({"name": "sm_list_namespaces", "passed": True, "count": namespaces.get("count", len(namespaces.get("namespaces", [])))})
        if not args.json:
            print(f"PASS sm_list_namespaces count={smoke[-1]['count']}")

    profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    if profile in {"standard", "full"}:
        sessions = rpc_call("sm_list_sessions", {"limit": 1})
        if not sessions or not sessions.get("ok"):
            if args.json:
                print(json.dumps({"ok": False, "error": "sm_list_sessions smoke failed"}, indent=2))
            else:
                print("FAIL sm_list_sessions smoke")
            return 1
        smoke.append({"name": "sm_list_sessions", "passed": True, "count": sessions.get("count", 0)})
        if not args.json:
            print(f"PASS sm_list_sessions count={smoke[-1]['count']}")
    elif not args.json:
        print("SKIP sm_list_sessions lean profile")

    for case in cases:
        result = rpc_call("sm_search", {"query": case["query"], "top_k": args.top_k})
        hits = gated_hits((result or {}).get("results") or []) if result and result.get("ok") else []
        haystack = "\n".join(str(hit.get("content") or "").lower() for hit in hits)
        expected = [str(item).lower() for item in case.get("expected", [])]
        matched = [needle for needle in expected if needle in haystack]
        passed = bool(hits) and len(matched) == len(expected)
        failures += 0 if passed else 1
        row = {
            "name": case.get("name", case["query"]),
            "passed": passed,
            "gated_hits": len(hits),
            "top_score": float((hits[0].get("cosine_similarity") or hits[0].get("score") or 0)) if hits else 0.0,
            "matched": matched,
            "expected": expected,
        }
        output.append(row)

    for case in HOOK_CASES:
        text = run_hook(case["prompt"])
        injected = bool(text)
        haystack = text.lower()
        missing = [s for s in case.get("must_include", []) if s.lower() not in haystack]
        forbidden = [s for s in case.get("must_not_include", []) if s.lower() in haystack]
        passed = injected == bool(case["should_inject"]) and not missing and not forbidden
        failures += 0 if passed else 1
        hook_output.append(
            {
                "name": case["name"],
                "passed": passed,
                "injected": injected,
                "missing": missing,
                "forbidden": forbidden,
            }
        )

    if args.json:
        print(json.dumps({"ok": failures == 0, "smoke": smoke, "results": output, "hook_results": hook_output}, indent=2))
    else:
        for row in output:
            status = "PASS" if row["passed"] else "FAIL"
            print(f"{status} {row['name']} hits={row['gated_hits']} top={row['top_score']:.3f}")
            if not row["passed"]:
                print(f"     matched={row['matched']} expected={row['expected']}")
        for row in hook_output:
            status = "PASS" if row["passed"] else "FAIL"
            print(f"{status} {row['name']} injected={row['injected']}")
            if not row["passed"]:
                print(f"     missing={row['missing']} forbidden={row['forbidden']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
