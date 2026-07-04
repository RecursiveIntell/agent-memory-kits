#!/usr/bin/env python3
"""Build a release-gate proof packet from command receipts and claim dispositions.

The packet is deliberately mechanical: it joins command receipt JSON with claim and
claim-disposition JSON, records stable SHA-256 digests for every source file, and
fails closed unless the final disposition is ``promote``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "semantic-memory-agent-kit-proof-packet-v1"
PROMOTE = "promote"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def source_record(path: Path, kind: str) -> dict[str, Any]:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    return {
        "kind": kind,
        "path": str(path),
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "json": data,
    }


def disposition_value(disposition_json: Any) -> str:
    if isinstance(disposition_json, str):
        return disposition_json
    if not isinstance(disposition_json, dict):
        return ""
    for key in ("disposition", "result", "status", "decision"):
        value = disposition_json.get(key)
        if isinstance(value, str):
            return value
    nested = disposition_json.get("verification")
    if isinstance(nested, dict):
        return disposition_value(nested)
    return ""


def command_passed(receipt_json: Any) -> bool | None:
    if not isinstance(receipt_json, dict):
        return None
    if isinstance(receipt_json.get("passed"), bool):
        return receipt_json["passed"]
    if isinstance(receipt_json.get("success"), bool):
        return receipt_json["success"]
    rc = receipt_json.get("returncode", receipt_json.get("exit_code"))
    if isinstance(rc, int):
        return rc == 0
    return None


def build_packet(command_receipts: list[Path], claim_json: Path, disposition_json: Path) -> tuple[dict[str, Any], bool]:
    commands = [source_record(path, "command_receipt") for path in command_receipts]
    claim = source_record(claim_json, "claim_json")
    disposition = source_record(disposition_json, "disposition_json")
    disposition_text = disposition_value(disposition["json"]).lower().strip()
    command_statuses = [command_passed(item["json"]) for item in commands]
    commands_passed = all(status is not False for status in command_statuses)
    gate_promoted = disposition_text == PROMOTE and commands_passed
    packet = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gate_promoted": gate_promoted,
        "disposition": disposition_text,
        "commands_passed": commands_passed,
        "command_receipts": commands,
        "claim": claim,
        "disposition_record": disposition,
    }
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
    packet["packet_sha256"] = sha256_bytes(canonical)
    return packet, gate_promoted


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Join command receipts with claim/disposition JSON into a release-gate proof packet.")
    ap.add_argument("--command-receipt", action="append", default=[], help="JSON command receipt path. Repeat for fmt/clippy/test/etc.")
    ap.add_argument("--claim-json", required=True, help="Claim JSON path.")
    ap.add_argument("--disposition-json", required=True, help="Disposition/verification JSON path. Must resolve to disposition=promote.")
    ap.add_argument("--out", required=True, help="Output proof packet JSON path.")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.command_receipt:
        print("at least one --command-receipt is required", file=sys.stderr)
        return 2
    try:
        packet, promoted = build_packet(
            [Path(item).expanduser() for item in args.command_receipt],
            Path(args.claim_json).expanduser(),
            Path(args.disposition_json).expanduser(),
        )
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"proof packet failed: {exc}", file=sys.stderr)
        return 2
    print(f"proof packet: {out}")
    if not promoted:
        print("release gate not promoted: disposition must be promote and command receipts must not fail", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
