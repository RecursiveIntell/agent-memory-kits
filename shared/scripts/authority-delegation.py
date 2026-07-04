#!/usr/bin/env python3
"""Authority-delegation lease system — create and verify time-bounded leases."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_lease(args: argparse.Namespace) -> int:
    created_at = _now()
    expires_at = created_at + timedelta(minutes=args.duration_mins)
    lease = {
        "schema": "AuthorityLeaseV1",
        "lease_id": f"lease:{uuid.uuid4().hex[:16]}",
        "operator": args.operator,
        "delegate": args.delegate,
        "capabilities": [c.strip() for c in args.capabilities.split(",") if c.strip()],
        "created_at": _iso(created_at),
        "expires_at": _iso(expires_at),
    }
    # Append to store (create parent dirs if needed)
    store_dir = os.path.dirname(args.store)
    if store_dir:
        os.makedirs(store_dir, exist_ok=True)
    with open(args.store, "a", encoding="utf-8") as f:
        f.write(json.dumps(lease) + "\n")
    print(json.dumps(lease))
    return 0


def _read_leases(store: str) -> list[dict]:
    leases: list[dict] = []
    if not os.path.exists(store):
        return leases
    with open(store, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                leases.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return leases


def _is_expired(lease: dict) -> bool:
    expires_str = lease.get("expires_at", "")
    if not expires_str:
        return True
    try:
        expires_at = datetime.strptime(expires_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return _now() >= expires_at


def verify_lease(args: argparse.Namespace) -> int:
    leases = _read_leases(args.store)
    if not leases:
        print(json.dumps({"valid": False, "reason": "no leases found in store"}))
        return 1

    # Find latest matching lease for this delegate (by created_at, descending)
    candidate_leases = [l for l in leases if l.get("delegate") == args.delegate]
    candidate_leases.sort(key=lambda l: l.get("created_at", ""), reverse=True)

    for lease in candidate_leases:
        if args.capability not in lease.get("capabilities", []):
            continue  # doesn't include this capability
        if _is_expired(lease):
            continue  # expired, keep looking for a newer non-expired one
        print(json.dumps({"valid": True, "reason": "active lease found"}))
        return 0

    # Determine why we failed
    has_delegate = any(l.get("delegate") == args.delegate for l in leases)
    if not has_delegate:
        print(json.dumps({"valid": False, "reason": f"no lease found for delegate '{args.delegate}'"}))
    else:
        has_cap = any(
            args.capability in l.get("capabilities", [])
            for l in leases if l.get("delegate") == args.delegate
        )
        if not has_cap:
            print(json.dumps({"valid": False, "reason": f"capability '{args.capability}' not granted in any lease for delegate '{args.delegate}'"}))
        else:
            print(json.dumps({"valid": False, "reason": "all matching leases have expired"}))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authority-delegation lease system")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create-lease", help="Create a time-bounded authority lease")
    p_create.add_argument("--operator", required=True, help="Who is granting the lease")
    p_create.add_argument("--delegate", required=True, help="Who receives the lease (agent name)")
    p_create.add_argument("--capabilities", required=True, help="Comma-separated list of allowed capabilities")
    p_create.add_argument("--duration-mins", required=True, type=int, help="Lease duration in minutes")
    p_create.add_argument("--store", required=True, help="Path to JSONL file for lease storage")

    p_verify = sub.add_parser("verify-lease", help="Verify an active lease for a delegate+capability")
    p_verify.add_argument("--delegate", required=True, help="Agent name to check")
    p_verify.add_argument("--capability", required=True, help="Capability to check")
    p_verify.add_argument("--store", required=True, help="Path to JSONL lease store")

    args = parser.parse_args(argv)

    if args.command == "create-lease":
        return create_lease(args)
    elif args.command == "verify-lease":
        return verify_lease(args)
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())