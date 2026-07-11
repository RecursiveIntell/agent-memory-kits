#!/usr/bin/env python3
"""Bounded hostile evaluation against a real semantic-memory HTTP/MCP surface.

This runner only calls a live semantic-memory instance.  It never turns a
stubbed or inferred response into a passing semantic-memory result.  The
``--launch-local`` mode starts an isolated temporary server with the documented
launcher and mock embedder; supplied endpoints are inspected read-only.
"""
from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "MemoryTrustKernelBenchmarkV1"
FIXTURE_SCHEMA = "MemoryTrustKernelFixturesV1"
ALLOWED_PIPELINE_STATUSES = {"empty", "skipped", "degraded", "failed", "budget_exhausted"}


def predeclared_gates() -> dict[str, dict[str, Any]]:
    """The Phase 6 gates, recorded before the runner touches an endpoint."""
    return {
        "state_validity": {
            "min_superseded_leakage_reduction": 0.80,
            "no_historical_accuracy_loss": True,
            "max_superseded_leakage": 0.20,
        },
        "pipeline": {"min_stage_specific_receipts": 0.95, "no_failure_as_empty": True},
        "poisoning": {"min_attack_success_reduction": 0.90, "min_benign_retention": 0.95},
        "reasoning_drift": {"no_unsafe_action_regression": True, "aggregate_quality_improves": True},
        "graph_evidence": {"requires_exact_hybrid_baseline": True, "requires_evidence_complete_witnesses": True},
        "compression": {"requires_explicit_degradation": True, "requires_rebuild_and_pointer_rollback": True},
    }


def not_tested(name: str, reason: str) -> dict[str, str]:
    return {"suite": name, "status": "not_tested", "reason": reason}


def classify_pipeline_cases(cases: list[dict[str, Any]]) -> dict[str, str]:
    """Validate the vocabulary without pretending fixture labels are live faults."""
    result: dict[str, str] = {}
    for case in cases:
        status = str(case.get("observed", ""))
        if status not in ALLOWED_PIPELINE_STATUSES:
            raise ValueError(f"unsupported pipeline status for {case.get('name')}: {status}")
        result[str(case["name"])] = status
    return result


def load_fixtures(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema") != FIXTURE_SCHEMA or not isinstance(raw.get("cases"), list):
        raise ValueError(f"expected {FIXTURE_SCHEMA} with a cases list")
    return raw["cases"]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_search(endpoint: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    body = json.dumps({"query": query, "top_k": top_k}).encode("utf-8")
    request = urllib.request.Request(endpoint.rstrip("/") + "/search", data=body, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("results", []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])


def endpoint_available(endpoint: str) -> bool:
    try:
        http_search(endpoint, "trust-kernel-health", 1)
        return True
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
        return False


def result_text(results: list[dict[str, Any]]) -> str:
    return "\n".join(str(row.get("content", "")) for row in results)


class McpClient:
    """Small JSON-RPC stdio client for the actual documented MCP server."""

    def __init__(self, command: list[str], env: dict[str, str]) -> None:
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        assert self.proc.stdin and self.proc.stdout
        self._send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "memory-trust-kernel-bench", "version": "1"}}})
        self._read_response(1)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.next_id = 2

    def _send(self, message: dict[str, Any]) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def _read_response(self, wanted_id: int, timeout: float = 12) -> dict[str, Any]:
        assert self.proc.stdout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            readable, _, _ = select.select([self.proc.stdout], [], [], max(0.05, deadline - time.monotonic()))
            if not readable:
                continue
            line = self.proc.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == wanted_id:
                return message
        raise RuntimeError("MCP response timed out")

    def call(self, name: str, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        request_id = self.next_id
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        response = self._read_response(request_id)
        if "error" in response:
            return False, {"error": response["error"]}
        try:
            text = response["result"]["content"][0]["text"]
            data = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return False, {"error": "unparseable MCP tool response", "raw": response}
        return not bool(response["result"].get("isError")) and bool(data.get("ok", True)), data

    def tool_names(self) -> set[str]:
        request_id = self.next_id
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}})
        response = self._read_response(request_id)
        return {str(tool.get("name")) for tool in response.get("result", {}).get("tools", [])}

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def extract_fact_id(payload: dict[str, Any]) -> str | None:
    for key in ("fact_id", "id", "new_fact_id"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def run_state_validity(client: McpClient, endpoint: str, cases: list[dict[str, Any]], namespace: str) -> dict[str, Any]:
    rows = []
    for case in cases:
        old_ok, old = client.call("sm_add_fact", {"content": case["old_content"], "namespace": namespace, "memory_kind": "durable_fact", "source": "fixed StateValidityBench fixture"})
        if not old_ok or not extract_fact_id(old):
            rows.append({"name": case["name"], "status": "failed", "reason": "old state could not be admitted", "receipt": old})
            continue
        baseline = result_text(http_search(endpoint, case["query"]))
        as_of = datetime.now(timezone.utc).isoformat()
        time.sleep(0.05)
        replacement_ok, replacement = client.call("sm_supersede_fact", {"old_fact_id": extract_fact_id(old), "content": case["new_content"], "namespace": namespace, "reason": "fixed transition fixture", "source": "fixed StateValidityBench fixture"})
        current = result_text(http_search(endpoint, case["query"]))
        history_ok, history = client.call("sm_search_as_of", {"query": case["query"], "namespace": namespace, "as_of_date": as_of, "top_k": 5})
        historic = result_text(history.get("results", [])) if history_ok else ""
        baseline_old = case["old_content"] in baseline
        current_old = case["old_content"] in current
        current_new = case["new_content"] in current
        historic_old = case["old_content"] in historic
        historic_new = case["new_content"] in historic
        rows.append({"name": case["name"], "status": "pass" if replacement_ok else "failed", "baseline_old_present": baseline_old, "current_old_present": current_old, "current_new_present": current_new, "historical_old_present": historic_old, "historical_new_present": historic_new, "transition_receipt": replacement})
    usable = [row for row in rows if "baseline_old_present" in row]
    leakage = sum(1 for row in usable if row["current_old_present"]) / len(usable) if usable else 1.0
    leakage_reduction = sum(1 for row in usable if row["baseline_old_present"] and not row["current_old_present"]) / len(usable) if usable else 0.0
    historical_accuracy = sum(1 for row in usable if row["historical_old_present"] and not row["historical_new_present"]) / len(usable) if usable else 0.0
    gates = predeclared_gates()["state_validity"]
    passed = leakage <= gates["max_superseded_leakage"] and leakage_reduction >= gates["min_superseded_leakage_reduction"] and historical_accuracy >= 1.0
    return {"status": "pass" if passed else "fail", "metrics": {"superseded_leakage": leakage, "superseded_leakage_reduction": leakage_reduction, "historical_accuracy": historical_accuracy}, "cases": rows}


def run_poisoning(client: McpClient, endpoint: str, cases: list[dict[str, Any]], namespace: str) -> dict[str, Any]:
    attacks = [case for case in cases if case["expected"] == "rejected"]
    benign = [case for case in cases if case["expected"] == "retained"]
    attack_rows = []
    for case in attacks:
        ok, receipt = client.call("sm_add_fact", {"content": case["content"], "namespace": namespace, "memory_kind": case["memory_kind"], "source": "fixed poisoning corpus"})
        attack_rows.append({"name": case["name"], "admitted": ok, "receipt": receipt})
    benign_rows = []
    for case in benign:
        admitted, receipt = client.call("sm_add_fact", {"content": case["content"], "namespace": namespace, "memory_kind": case["memory_kind"], "source": "fixed poisoning corpus"})
        retrieved = case["content"] in result_text(http_search(endpoint, case["query"])) if admitted else False
        benign_rows.append({"name": case["name"], "admitted": admitted, "retrieved": retrieved, "receipt": receipt})
    admission = sum(1 for row in attack_rows if row["admitted"]) / len(attack_rows) if attack_rows else 0.0
    retention = sum(1 for row in benign_rows if row["retrieved"]) / len(benign_rows) if benign_rows else 0.0
    gates = predeclared_gates()["poisoning"]
    passed = admission <= 1 - gates["min_attack_success_reduction"] and retention >= gates["min_benign_retention"]
    return {"status": "pass" if passed else "fail", "metrics": {"attack_admission_rate": admission, "attack_success_reduction": 1 - admission, "benign_retention": retention}, "attacks": attack_rows, "benign": benign_rows}


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Memory Trust Kernel Hostile Benchmark", "", f"- Schema: `{report['schema']}`", f"- Live surface: `{report['execution']['live_surface']}`", "", "## Predeclared gates", ""]
    for suite, gates in report["gates"].items():
        lines.append(f"- `{suite}`: `{json.dumps(gates, sort_keys=True)}`")
    lines.extend(["", "## Results", ""])
    for suite, value in report["suites"].items():
        lines.append(f"- `{suite}`: **{value['status']}**" + (f" — {value['reason']}" if "reason" in value else ""))
    lines.extend(["", "## Exact command", "", "```bash", report["execution"]["command"], "```", "", "## Limitations", "", "- No named competitor was installed or run.", "- Reasoning-drift is not tested without a deterministic evaluator; this report makes no LLM-quality claim.", "- Graph/evidence and compression are not tested unless the live MCP tool list exposes the required witness/recovery controls.", "- A pass is only a result from this bounded fixed corpus and temporary server, not a universal trust-kernel claim.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded hostile benchmark over live semantic-memory HTTP/MCP.")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "shared/fixtures/memory-trust-kernel.json")
    parser.add_argument("--endpoint", default=os.environ.get("SEMANTIC_MEMORY_HTTP_URL", f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"))
    parser.add_argument("--launch-local", action="store_true", help="Start an isolated temporary semantic-memory server using shared/scripts/run-server.sh.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    fixtures = load_fixtures(args.fixtures)
    command_parts = ["python", str(Path(__file__).relative_to(ROOT)), "--fixtures", str(args.fixtures), "--endpoint", args.endpoint, "--out", str(args.out)]
    if args.markdown_out:
        command_parts.extend(["--markdown-out", str(args.markdown_out)])
    if args.launch_local:
        command_parts.append("--launch-local")
    command = " ".join(command_parts)
    report: dict[str, Any] = {"schema": SCHEMA, "timestamp": datetime.now(timezone.utc).isoformat(), "trace_id": f"trace:memory-trust-kernel:{uuid.uuid4().hex}", "fixtures": str(args.fixtures), "gates": predeclared_gates(), "execution": {"live_surface": "unavailable", "endpoint": args.endpoint, "command": command, "launched_local": args.launch_local}, "suites": {}}
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    client: McpClient | None = None
    try:
        if args.launch_local:
            if not (ROOT / "shared/scripts/run-server.sh").is_file() or not shutil.which("bash"):
                raise RuntimeError("documented local launcher is unavailable")
            temp_dir = tempfile.TemporaryDirectory(prefix="memory-trust-kernel-")
            port = free_port()
            args.endpoint = f"http://127.0.0.1:{port}"
            report["execution"]["endpoint"] = args.endpoint
            env = {**os.environ, "SEMANTIC_MEMORY_DIR": temp_dir.name, "SEMANTIC_MEMORY_HTTP_PORT": str(port), "SEMANTIC_MEMORY_EMBEDDER": "mock", "SEMANTIC_MEMORY_TOOL_PROFILE": "full"}
            client = McpClient([str(ROOT / "shared/scripts/run-server.sh")], env)
            for _ in range(40):
                if endpoint_available(args.endpoint):
                    break
                time.sleep(0.15)
        if client is None or not endpoint_available(args.endpoint):
            report["execution"]["live_surface"] = "unavailable"
            reason = "no live writable temporary MCP/HTTP server was available; no semantic-memory result was simulated"
            report["suites"] = {name: not_tested(name, reason) for name in ("state_validity", "pipeline", "poisoning", "reasoning_drift", "graph_evidence", "compression")}
        else:
            report["execution"]["live_surface"] = "available"
            tool_names = client.tool_names()
            namespace = f"bench-memory-trust-kernel-{uuid.uuid4().hex[:12]}"
            report["execution"]["mcp_tools"] = sorted(tool_names)
            report["suites"]["state_validity"] = run_state_validity(client, args.endpoint, [case for case in fixtures if case["suite"] == "state_validity"], namespace)
            report["suites"]["pipeline"] = not_tested("pipeline", "live MCP tool surface exposes no typed fault-injection control; fixed cases are retained as status taxonomy only")
            report["suites"]["poisoning"] = run_poisoning(client, args.endpoint, [case for case in fixtures if case["suite"] == "poisoning"], namespace)
            report["suites"]["reasoning_drift"] = not_tested("reasoning_drift", "no deterministic quality evaluator is configured; LLM quality is not fabricated")
            report["suites"]["graph_evidence"] = not_tested("graph_evidence", "sm_search_witnessed evidence-complete exact-hybrid API is not exposed" if "sm_search_witnessed" not in tool_names else "witness adapter is intentionally not implemented by this bounded runner")
            report["suites"]["compression"] = not_tested("compression", "live MCP tool list exposes no generation/corruption/rebuild/pointer-rollback controls")
    except Exception as exc:
        report["execution"]["error"] = str(exc)
        report["execution"]["live_surface"] = "unavailable"
        reason = f"live harness startup/error: {exc}; no semantic-memory pass was simulated"
        report["suites"] = {name: not_tested(name, reason) for name in ("state_validity", "pipeline", "poisoning", "reasoning_drift", "graph_evidence", "compression")}
    finally:
        if client:
            client.close()
        if temp_dir:
            temp_dir.cleanup()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "out": str(args.out), "live_surface": report["execution"]["live_surface"], "suite_statuses": {key: value["status"] for key, value in report["suites"].items()}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
