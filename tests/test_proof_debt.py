#!/usr/bin/env python3
"""Tests for proof_debt.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared", "scripts"))
from proof_debt import ProofDebtBudget, RiskClass, PaymentMethod


class TestProofDebt(unittest.TestCase):
    def test_incur_creates_entry(self) -> None:
        """incur should create an unpaid entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget = ProofDebtBudget(os.path.join(tmpdir, "debt.jsonl"))
            entry_id = budget.incur("claim-1", "general", RiskClass.MEDIUM)
            self.assertTrue(entry_id.startswith("debt:"))
            self.assertEqual(budget.unpaid_count(), 1)
            self.assertEqual(budget.unpaid_count(RiskClass.MEDIUM), 1)
            self.assertEqual(budget.unpaid_count(RiskClass.LOW), 0)

    def test_pay_marks_entry_paid(self) -> None:
        """pay should mark an entry as paid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget = ProofDebtBudget(os.path.join(tmpdir, "debt.jsonl"))
            entry_id = budget.incur("claim-1", "general", RiskClass.MEDIUM)
            paid = budget.pay(entry_id, PaymentMethod.TEST_PASSED)
            self.assertTrue(paid)
            self.assertEqual(budget.unpaid_count(), 0)

    def test_is_blocked_when_threshold_exceeded(self) -> None:
        """is_blocked should be True when unpaid count exceeds threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget = ProofDebtBudget(os.path.join(tmpdir, "debt.jsonl"))
            # CRITICAL threshold is 5
            for i in range(5):
                budget.incur(f"claim-{i}", "general", RiskClass.CRITICAL)
            self.assertTrue(budget.is_blocked(RiskClass.CRITICAL))

    def test_not_blocked_below_threshold(self) -> None:
        """is_blocked should be False when unpaid count is below threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget = ProofDebtBudget(os.path.join(tmpdir, "debt.jsonl"))
            for i in range(3):
                budget.incur(f"claim-{i}", "general", RiskClass.CRITICAL)
            self.assertFalse(budget.is_blocked(RiskClass.CRITICAL))

    def test_persistence_across_instances(self) -> None:
        """Entries should survive across budget instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = os.path.join(tmpdir, "debt.jsonl")
            budget1 = ProofDebtBudget(store)
            budget1.incur("claim-1", "general", RiskClass.MEDIUM)
            budget2 = ProofDebtBudget(store)
            self.assertEqual(budget2.unpaid_count(), 1)

    def test_status_returns_summary(self) -> None:
        """status should return a summary with schema and blocked flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget = ProofDebtBudget(os.path.join(tmpdir, "debt.jsonl"))
            budget.incur("claim-1", "general", RiskClass.LOW)
            status = budget.status()
            self.assertEqual(status["schema"], "ProofDebtStatusV1")
            self.assertEqual(status["unpaid_total"], 1)
            self.assertIn("blocked", status)
            self.assertIn("thresholds", status)

    def test_cli_incur_and_status(self) -> None:
        """CLI incur + status should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = os.path.join(tmpdir, "debt.jsonl")
            script = os.path.join(os.path.dirname(__file__), "..", "shared", "scripts", "proof_debt.py")
            result = subprocess.run(
                [sys.executable, script, "--store", store, "incur",
                 "--claim-id", "claim-1", "--namespace", "general", "--risk-class", "medium"],
                capture_output=True, text=True, timeout=10
            )
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertTrue(data["incurred"])

            result = subprocess.run(
                [sys.executable, script, "--store", store, "status"],
                capture_output=True, text=True, timeout=10
            )
            status = json.loads(result.stdout)
            self.assertEqual(status["unpaid_total"], 1)


if __name__ == "__main__":
    unittest.main()