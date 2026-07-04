#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

DEFAULT_OUT = Path.home() / ".local/share/semantic-memory-agent-kits/receipts"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _trace_id() -> str:
    """Generate a stack-ids-compatible trace ID."""
    import uuid
    return f"trace:evidence-workbench:{uuid.uuid4().hex[:16]}"


def http_add_fact(content: str, namespace: str, source: str, timeout: float = 3.0) -> dict | None:
    base = os.environ.get("SEMANTIC_MEMORY_HTTP_URL") or f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"
    body = json.dumps({"content": content, "namespace": namespace, "source": source}, separators=(",", ":")).encode()
    req = request.Request(base.rstrip("/") + "/add", data=body, headers={"content-type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def run_command(cmd: str, cwd: Path, timeout: int) -> dict:
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(cmd, shell=True, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, check=False)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        exit_code = 124
        timed_out = True
    finished = datetime.now(timezone.utc)
    combined = stdout + "\n" + stderr
    return {
        "command": cmd,
        "cwd": str(cwd),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "combined_sha256": sha256_text(combined),
        "stdout_preview": stdout[-4000:],
        "stderr_preview": stderr[-4000:],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run command gates and emit an Agent Evidence Workbench proof packet.")
    ap.add_argument("--claim", required=True, help="Claim being evaluated, e.g. 'plugin P0 gates pass'")
    ap.add_argument("--cmd", action="append", required=True, help="Shell command to run. Repeat for multiple gates.")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--namespace", default="evidence-workbench")
    ap.add_argument("--no-memory", action="store_true", help="Do not write the proof packet summary to semantic-memory HTTP /add")
    ap.add_argument("--write-claim-ledger", action="store_true", help="Write claim + evidence to claim-ledger MCP if available")
    args = ap.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
    command_receipts = [run_command(cmd, cwd, args.timeout) for cmd in args.cmd]
    all_passed = all(row["exit_code"] == 0 and not row["timed_out"] for row in command_receipts)
    disposition = "promote" if all_passed else "reject"
    evidence_refs = [f"sha256:{row['combined_sha256']}" for row in command_receipts]
    packet = {
        "schema": "AgentEvidenceWorkbenchProofPacketV1",
        "trace_id": _trace_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim": args.claim,
        "risk_class": "medium",
        "disposition": disposition,
        "evidence_refs": evidence_refs,
        "commands": command_receipts,
        "claim_boundary": "Command receipts prove the listed gates ran with the captured exit codes; they do not prove untested behavior.",
    }
    packet_json = json.dumps(packet, sort_keys=True)
    packet["proof_packet_sha256"] = sha256_text(packet_json)
    if not args.no_memory:
        summary = f"Evidence Workbench proof packet: claim={args.claim!r} disposition={disposition} commands={len(command_receipts)} packet_sha256={packet['proof_packet_sha256']}"
        mem = http_add_fact(summary, args.namespace, "agent-evidence-workbench")
        if mem:
            packet["semantic_memory_result"] = mem
    if args.write_claim_ledger:
        try:
            import importlib.util
            rgv2_path = Path(__file__).resolve().parent / "release-gate-v2.py"
            spec = importlib.util.spec_from_file_location("release_gate_v2", rgv2_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                cl_result = mod.claim_ledger_call("cl_create_claim", {
                    "claim_text": args.claim,
                    "evidence_refs": evidence_refs,
                    "risk_class": "medium",
                })
                packet["claim_ledger_result"] = cl_result or {"available": False, "error": "claim-ledger MCP not reachable"}
            else:
                packet["claim_ledger_result"] = {"available": False, "error": "could not load release-gate-v2"}
        except Exception as exc:
            packet["claim_ledger_result"] = {"available": False, "error": str(exc)}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"evidence-workbench-{stamp}.json"
    out.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    print(json.dumps({"ok": all_passed, "disposition": disposition, "receipt": str(out), "packet_sha256": packet["proof_packet_sha256"]}, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
