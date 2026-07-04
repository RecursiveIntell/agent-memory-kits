#!/usr/bin/env python3
"""proof_debt.py — proof-debt entropy budget for tracking unverified claims.

Every time a fact is promoted, proof-debt is incurred. Debt is paid when
the claim is verified (test passed, audit passed, evidence provided).
Blocks promotion when debt exceeds threshold for the risk class.

Usage as module:
    from proof_debt import ProofDebtBudget, RiskClass
    budget = ProofDebtBudget("/path/to/proof-debt.jsonl")
    entry_id = budget.incur("claim-123", "general", RiskClass.MEDIUM)
    if budget.is_blocked(RiskClass.MEDIUM):
        # block promotion
    budget.pay(entry_id, PaymentMethod.TEST_PASSED)

Usage as CLI:
    python proof_debt.py incur --claim-id X --namespace general --risk-class medium --store /path
    python proof_debt.py pay --entry-id Y --method test_passed --store /path
    python proof_debt.py status --store /path
    python proof_debt.py is-blocked --risk-class medium --store /path
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class RiskClass(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PaymentMethod(Enum):
    TEST_PASSED = "test_passed"
    AUDIT_PASSED = "audit_passed"
    EVIDENCE_PROVIDED = "evidence_provided"
    SUPERSEDED = "superseded"
    CONTRADICTION_FOUND = "contradiction_found"
    EXTERNAL_EVIDENCE = "external_evidence"


DEFAULT_THRESHOLDS = {
    RiskClass.LOW: 100,
    RiskClass.MEDIUM: 50,
    RiskClass.HIGH: 20,
    RiskClass.CRITICAL: 5,
}


@dataclass
class ProofDebtEntry:
    entry_id: str
    claim_id: str
    namespace: str
    risk_class: str
    incurred_at: str
    paid: bool = False
    paid_at: str | None = None
    payment_method: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class ProofDebtBudget:
    """Tracks cumulative unverified claims and blocks promotion when debt exceeds threshold."""

    def __init__(self, store_path: str, thresholds: dict[RiskClass, int] | None = None):
        self.store_path = Path(store_path)
        self.thresholds = thresholds or dict(DEFAULT_THRESHOLDS)
        self.entries: list[ProofDebtEntry] = []
        self._load()

    def _load(self) -> None:
        """Load entries from JSONL store."""
        if not self.store_path.exists():
            return
        try:
            with open(self.store_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self.entries.append(ProofDebtEntry(
                        entry_id=data["entry_id"],
                        claim_id=data["claim_id"],
                        namespace=data["namespace"],
                        risk_class=data["risk_class"],
                        incurred_at=data["incurred_at"],
                        paid=data.get("paid", False),
                        paid_at=data.get("paid_at"),
                        payment_method=data.get("payment_method"),
                    ))
        except Exception:
            pass

    def _append(self, entry: ProofDebtEntry) -> None:
        """Append entry to JSONL store."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def incur(self, claim_id: str, namespace: str, risk_class: RiskClass) -> str:
        """Record new debt. Returns entry ID."""
        entry = ProofDebtEntry(
            entry_id=f"debt:{uuid.uuid4().hex[:16]}",
            claim_id=claim_id,
            namespace=namespace,
            risk_class=risk_class.value,
            incurred_at=datetime.now(timezone.utc).isoformat(),
        )
        self.entries.append(entry)
        self._append(entry)
        return entry.entry_id

    def pay(self, entry_id: str, method: PaymentMethod) -> bool:
        """Mark debt as paid. Returns True if entry was found and paid."""
        for entry in self.entries:
            if entry.entry_id == entry_id and not entry.paid:
                entry.paid = True
                entry.paid_at = datetime.now(timezone.utc).isoformat()
                entry.payment_method = method.value
                # Rewrite the store file
                self._rewrite_store()
                return True
        return False

    def _rewrite_store(self) -> None:
        """Rewrite the entire store file."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w") as f:
            for entry in self.entries:
                f.write(json.dumps(entry.to_dict()) + "\n")

    def unpaid_count(self, risk_class: RiskClass | None = None) -> int:
        """Count unpaid entries, optionally filtered by risk class."""
        count = 0
        for entry in self.entries:
            if not entry.paid:
                if risk_class is None or entry.risk_class == risk_class.value:
                    count += 1
        return count

    def is_blocked(self, risk_class: RiskClass) -> bool:
        """True if unpaid debt exceeds threshold for the risk class."""
        unpaid = self.unpaid_count(risk_class)
        threshold = self.thresholds.get(risk_class, DEFAULT_THRESHOLDS[risk_class])
        return unpaid >= threshold

    def status(self) -> dict:
        """Return current debt summary."""
        return {
            "schema": "ProofDebtStatusV1",
            "total_entries": len(self.entries),
            "unpaid_total": self.unpaid_count(),
            "unpaid_by_risk": {
                rc.value: self.unpaid_count(rc) for rc in RiskClass
            },
            "thresholds": {
                rc.value: self.thresholds.get(rc, DEFAULT_THRESHOLDS[rc])
                for rc in RiskClass
            },
            "blocked": {
                rc.value: self.is_blocked(rc) for rc in RiskClass
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Proof-debt budget tracker")
    parser.add_argument("--store", required=True, help="Path to JSONL store")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("incur")
    p.add_argument("--claim-id", required=True)
    p.add_argument("--namespace", required=True)
    p.add_argument("--risk-class", required=True, choices=["low", "medium", "high", "critical"])
    p.set_defaults(func="incur")

    p = sub.add_parser("pay")
    p.add_argument("--entry-id", required=True)
    p.add_argument("--method", required=True, choices=[m.value for m in PaymentMethod])
    p.set_defaults(func="pay")

    p = sub.add_parser("status")
    p.set_defaults(func="status")

    p = sub.add_parser("is-blocked")
    p.add_argument("--risk-class", required=True, choices=["low", "medium", "high", "critical"])
    p.set_defaults(func="is-blocked")

    args = parser.parse_args()
    budget = ProofDebtBudget(args.store)

    if args.command == "incur":
        rc = RiskClass(args.risk_class)
        entry_id = budget.incur(args.claim_id, args.namespace, rc)
        print(json.dumps({"entry_id": entry_id, "incurred": True}))

    elif args.command == "pay":
        method = PaymentMethod(args.method)
        paid = budget.pay(args.entry_id, method)
        print(json.dumps({"paid": paid}))

    elif args.command == "status":
        print(json.dumps(budget.status(), indent=2))

    elif args.command == "is-blocked":
        rc = RiskClass(args.risk_class)
        blocked = budget.is_blocked(rc)
        print(json.dumps({"blocked": blocked, "unpaid": budget.unpaid_count(rc)}))
        if blocked:
            sys.exit(1)


if __name__ == "__main__":
    main()