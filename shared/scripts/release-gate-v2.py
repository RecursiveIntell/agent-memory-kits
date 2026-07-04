#!/usr/bin/env python3
"""release-gate-v2.py — Evidence Workbench v2 with claim-ledger + verification pipeline.

Upgrades evidence-workbench.py from a command-runner into a proof packet pipeline
that joins command receipts, claim adjudication, and optional claim-ledger storage.

Key additions over v1:
  - VerificationCaseV1 structure (case_id, claim, risk_class, check_plan)
  - CheckPlan with per-command attempt records
  - Adjudication: promote/reject/quarantine/defer based on command results
  - Optional --write-claim-ledger to store claim + evidence in claim-ledger MCP
  - stack-ids-compatible trace IDs
  - packet_sha256 for tamper-evidence

Usage:
  python release-gate-v2.py --claim "tests pass" --cmd "pytest" --cwd . --out-dir /tmp/proof --no-memory
  python release-gate-v2.py --claim "release ready" --cmd "cargo test" --cmd "cargo clippy" --write-claim-ledger --out-dir /tmp/proof
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

DEFAULT_OUT = Path.home() / ".local/share/semantic-memory-agent-kits/receipts"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def generate_trace_id(scope: str = "release-gate") -> str:
    return f"trace:{scope}:{uuid.uuid4().hex[:16]}"


def git_commit(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def http_add_fact(content: str, namespace: str, source: str, timeout: float = 3.0) -> dict | None:
    base = os.environ.get("SEMANTIC_MEMORY_HTTP_URL") or f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"
    body = json.dumps(
        {"content": content, "namespace": namespace, "source": source},
        separators=(",", ":"),
    ).encode()
    req = request.Request(
        base.rstrip("/") + "/add",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def claim_ledger_call(method: str, params: dict, timeout: float = 5.0) -> dict | None:
    """Call claim-ledger MCP via HTTP if available."""
    base = os.environ.get("CLAIM_LEDGER_HTTP_URL") or "http://127.0.0.1:1740"
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1})
    req = request.Request(
        base.rstrip("/") + "/rpc",
        data=body.encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("result")
    except Exception:
        return None


def run_command(cmd: str, cwd: Path, timeout: int) -> dict:
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, check=False
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
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


def adjudicate(command_receipts: list[dict]) -> tuple[str, str]:
    """Determine disposition from command receipts. Returns (disposition, reason)."""
    failed = [r for r in command_receipts if r["exit_code"] != 0 or r["timed_out"]]
    if not failed:
        return "promote", "all commands passed"
    if any(r["timed_out"] for r in failed):
        return "quarantine", f"{len(failed)} command(s) timed out"
    return "reject", f"{len(failed)} command(s) failed with non-zero exit"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Release Gate v2 — proof packet pipeline with claim-ledger + verification"
    )
    ap.add_argument("--claim", required=True, help="Claim being evaluated")
    ap.add_argument("--cmd", action="append", required=True, help="Shell command to run. Repeat for multiple gates.")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--namespace", default="release-gate")
    ap.add_argument("--no-memory", action="store_true", help="Do not write summary to semantic-memory")
    ap.add_argument("--write-claim-ledger", action="store_true", help="Write claim + evidence to claim-ledger MCP")
    ap.add_argument("--risk-class", default="medium", choices=["low", "medium", "high", "critical"])
    args = ap.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_id = generate_trace_id("release-gate")
    case_id = f"case:{uuid.uuid4().hex[:16]}"

    # Run commands
    command_receipts = [run_command(cmd, cwd, args.timeout) for cmd in args.cmd]

    # Adjudicate
    disposition, reason = adjudicate(command_receipts)

    # Proof-debt check: if promoting, check if proof debt blocks this risk class
    proof_debt_entry_id = None
    proof_debt_error = None
    if disposition == "promote":
        try:
            import importlib.util as _ilu
            pd_path = Path(__file__).resolve().parent / "proof_debt.py"
            _spec = _ilu.spec_from_file_location("proof_debt", pd_path)
            if _spec and _spec.loader:
                _pd_mod = _ilu.module_from_spec(_spec)
                sys.modules["proof_debt"] = _pd_mod
                _spec.loader.exec_module(_pd_mod)
                pd_store = os.environ.get("RI_PROOF_DEBT_STORE", str(Path.home() / ".local/share/semantic-memory/proof-debt.jsonl"))
                budget = _pd_mod.ProofDebtBudget(pd_store)
                risk_class_map = {"low": _pd_mod.RiskClass.LOW, "medium": _pd_mod.RiskClass.MEDIUM,
                                  "high": _pd_mod.RiskClass.HIGH, "critical": _pd_mod.RiskClass.CRITICAL}
                rc = risk_class_map.get(args.risk_class, _pd_mod.RiskClass.MEDIUM)
                if budget.is_blocked(rc):
                    disposition = "quarantine"
                    reason = f"proof debt exceeds threshold for {args.risk_class} ({budget.unpaid_count(rc)} unpaid)"
                else:
                    # Incur debt for this promotion
                    proof_debt_entry_id = budget.incur(case_id, args.namespace, rc)
        except Exception as exc:
            # Fail open — don't block promotion on proof_debt errors
            proof_debt_error = str(exc)

    # Build verification case
    evidence_refs = [f"sha256:{r['combined_sha256']}" for r in command_receipts]
    verification_case = {
        "schema": "ReleaseGateCaseV1",
        "case_id": case_id,
        "claim": args.claim,
        "risk_class": args.risk_class,
        "check_plan": {
            "commands": args.cmd,
            "cwd": str(cwd),
            "timeout": args.timeout,
        },
        "attempts": command_receipts,
        "evidence_refs": evidence_refs,
    }

    # Build proof packet
    packet = {
        "schema": "ReleaseGateProofPacketV1",
        "trace_id": trace_id,
        "case_id": case_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim": args.claim,
        "risk_class": args.risk_class,
        "disposition": disposition,
        "disposition_reason": reason,
        "verification_case": verification_case,
        "command_receipts": command_receipts,
        "evidence_refs": evidence_refs,
        "git_commit": git_commit(str(cwd)),
        "claim_boundary": "Command receipts prove the listed gates ran with the captured exit codes; they do not prove untested behavior or total correctness.",
    }
    packet_json = json.dumps(packet, sort_keys=True)
    packet["packet_sha256"] = sha256_text(packet_json)

    # Add proof-debt fields after packet hash (so they don't affect the hash)
    if proof_debt_entry_id:
        packet["proof_debt_entry_id"] = proof_debt_entry_id
    if proof_debt_error:
        packet["proof_debt_error"] = proof_debt_error

    # Optional: write to claim-ledger
    if args.write_claim_ledger:
        cl_result = claim_ledger_call("cl_create_claim", {
            "claim_text": args.claim,
            "evidence_refs": evidence_refs,
            "risk_class": args.risk_class,
        })
        if cl_result:
            packet["claim_ledger_result"] = cl_result
        else:
            packet["claim_ledger_result"] = {"available": False, "error": "claim-ledger MCP not reachable"}

    # Optional: write to semantic-memory
    if not args.no_memory:
        summary = (
            f"Release Gate v2: claim={args.claim!r} disposition={disposition} "
            f"commands={len(command_receipts)} packet_sha256={packet['packet_sha256']}"
        )
        mem = http_add_fact(summary, args.namespace, "release-gate-v2")
        if mem:
            packet["semantic_memory_result"] = mem

    # Write packet
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"release-gate-v2-{stamp}.json"
    out.write_text(json.dumps(packet, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": disposition == "promote",
                "disposition": disposition,
                "case_id": case_id,
                "trace_id": trace_id,
                "receipt": str(out),
                "packet_sha256": packet["packet_sha256"],
            },
            indent=2,
        )
    )
    return 0 if disposition == "promote" else 1


if __name__ == "__main__":
    raise SystemExit(main())