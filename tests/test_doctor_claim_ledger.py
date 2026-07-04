#!/usr/bin/env python3
"""Tests for claim-ledger integration in doctor deep."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

DOCTOR = os.path.join(
    os.path.dirname(__file__), "..", "shared", "scripts", "doctor_core.py"
)


class TestDoctorClaimLedger(unittest.TestCase):
    def test_deep_includes_claim_ledger_check(self) -> None:
        """Doctor --deep should include a claim-ledger verification check."""
        receipt_path = "/tmp/test-doctor-cl.json"
        result = subprocess.run(
            [sys.executable, DOCTOR, "--host", "hermes", "--deep",
             "--receipt", receipt_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        # Doctor should pass or warn (exit 0 or 1), not crash (exit 2)
        self.assertIn(result.returncode, [0, 1])
        if os.path.exists(receipt_path):
            with open(receipt_path) as f:
                receipt = json.load(f)
            checks = receipt.get("results", [])
            cl_checks = [
                c for c in checks
                if "claim" in c.get("label", "").lower()
                and "ledger" in c.get("label", "").lower()
            ]
            self.assertTrue(
                len(cl_checks) > 0,
                "No claim-ledger check in doctor deep results"
            )


if __name__ == "__main__":
    unittest.main()