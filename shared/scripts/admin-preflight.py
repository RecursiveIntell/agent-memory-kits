#!/usr/bin/env python3
"""Admin action preflight system — emit effect intents and execution receipts
for destructive admin operations.

Subcommands:
  preflight       Emit an EffectIntentV1 JSON before running an operation.
  postflight      Emit an EffectExecutionReceiptV1 JSON after an operation.
  verify-receipt  Validate a preflight receipt JSON.

Exit codes:
  0 — allowed / valid / success
  1 — blocked / invalid / failure
"""
from __future__ import annotations

import argparse
import json
import uuid
import sys
from datetime import datetime, timezone
try:
    from license_client import require_license_state
except Exception:
    require_license_state = None  # type: ignore

RISK_LEVELS: dict[str, str] = {
    "delete_namespace": "critical",
    "delete_fact": "critical",
    "reembed_all": "high",
    "import_envelope": "medium",
    "reconcile": "low",
    "vacuum": "low",
    "reembed_missing": "low",
    "export_bundle": "low",
    "claim_ledger_export": "low",
    "verify_patch": "medium",
    "release_gate_promotion": "high",
}

VALID_OPERATIONS = set(RISK_LEVELS.keys())

HIGH_RISK_LEVELS = {"high", "critical"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------

def cmd_preflight(args: argparse.Namespace) -> int:
    operation: str = args.operation
    target: str = args.target
    operator: str = args.operator
    confirmed: bool = args.confirm

    if operation not in VALID_OPERATIONS:
        print(json.dumps({
            "blocked": True,
            "reason": f"unknown operation: {operation}",
        }))
        return 1

    risk_level = RISK_LEVELS[operation]

    if risk_level in HIGH_RISK_LEVELS and not confirmed:
        print(json.dumps({
            "blocked": True,
            "reason": f"confirmation required for {risk_level} operation",
        }))
        return 1

    license_state = require_license_state("admin-preflight") if require_license_state is not None else None
    intent = {
        "schema": "EffectIntentV1",
        "trace_id": f"trace:admin-preflight:{uuid.uuid4().hex[:16]}",
        "operation": operation,
        "target": target,
        "operator": operator,
        "risk_level": risk_level,
        "confirmed": confirmed,
        "timestamp": _iso_now(),
    }
    if license_state is not None:
        intent["license_state"] = license_state
    print(json.dumps(intent))
    return 0


# ---------------------------------------------------------------------------
# postflight
# ---------------------------------------------------------------------------

def cmd_postflight(args: argparse.Namespace) -> int:
    license_state = require_license_state("admin-preflight") if require_license_state is not None else None
    receipt = {
        "schema": "EffectExecutionReceiptV1",
        "operation": args.operation,
        "target": args.target,
        "exit_code": args.exit_code,
        "duration_secs": args.duration_secs,
        "timestamp": _iso_now(),
    }
    if license_state is not None:
        receipt["license_state"] = license_state
    print(json.dumps(receipt))
    return 0


# ---------------------------------------------------------------------------
# verify-receipt
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ("schema", "operation", "target", "operator", "risk_level")


def cmd_verify_receipt(args: argparse.Namespace) -> int:
    try:
        data = json.loads(args.receipt_json)
    except (json.JSONDecodeError, TypeError):
        print(json.dumps({"valid": False, "reason": "invalid JSON"}))
        return 1

    if not isinstance(data, dict):
        print(json.dumps({"valid": False, "reason": "not a JSON object"}))
        return 1

    if data.get("schema") != "EffectIntentV1":
        print(json.dumps({
            "valid": False,
            "reason": f"wrong schema: {data.get('schema')!r}",
        }))
        return 1

    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            print(json.dumps({
                "valid": False,
                "reason": f"missing field: {field}",
            }))
            return 1

    print(json.dumps({"valid": True}))
    return 0


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="admin-preflight",
        description="Admin action preflight / postflight / verify-receipt system.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- preflight ---
    pf = sub.add_parser("preflight", help="Emit an EffectIntentV1 before an operation.")
    pf.add_argument("--operation", required=True,
                    help="Operation name (e.g. delete_namespace, reembed_all).")
    pf.add_argument("--target", required=True,
                    help="Target of the operation (namespace, file path, etc.).")
    pf.add_argument("--operator", required=True,
                    help="Who is performing the operation.")
    pf.add_argument("--confirm", action="store_true",
                    help="Confirm high/critical risk operations.")
    pf.set_defaults(func=cmd_preflight)

    # --- postflight ---
    sf = sub.add_parser("postflight", help="Emit an EffectExecutionReceiptV1 after an operation.")
    sf.add_argument("--operation", required=True, help="Operation name.")
    sf.add_argument("--target", required=True, help="Target of the operation.")
    sf.add_argument("--exit-code", required=True, type=int, help="Exit code of the operation.")
    sf.add_argument("--duration-secs", required=False, type=float, default=None,
                    help="Duration of the operation in seconds.")
    sf.set_defaults(func=cmd_postflight)

    # --- verify-receipt ---
    vr = sub.add_parser("verify-receipt", help="Validate a preflight receipt JSON.")
    vr.add_argument("--receipt-json", required=True,
                    help="JSON string of the receipt to verify.")
    vr.set_defaults(func=cmd_verify_receipt)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())