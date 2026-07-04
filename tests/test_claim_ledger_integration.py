#!/usr/bin/env python3
"""Tests for claim-ledger integration across material plugin scripts."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest


class TestClaimLedgerIntegration(unittest.TestCase):
    def test_release_gate_v2_has_write_claim_ledger(self) -> None:
        """release-gate-v2 should have --write-claim-ledger flag."""
        script = os.path.join(
            os.path.dirname(__file__), "..", "shared", "scripts", "release-gate-v2.py"
        )
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn("--write-claim-ledger", result.stdout)

    def test_evidence_workbench_has_write_claim_ledger(self) -> None:
        """evidence-workbench.py should have --write-claim-ledger flag."""
        script = os.path.join(
            os.path.dirname(__file__), "..", "shared", "scripts", "evidence-workbench.py"
        )
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn("--write-claim-ledger", result.stdout)

    def test_verify_patch_has_write_claim_ledger(self) -> None:
        """verify-patch.py should have --write-claim-ledger flag."""
        script = os.path.join(
            os.path.dirname(__file__), "..", "shared", "scripts", "verify-patch.py"
        )
        if not os.path.exists(script):
            self.skipTest("verify-patch.py not yet created by subagent")
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn("--write-claim-ledger", result.stdout)

    def test_context_governor_audit_has_write_claim_ledger(self) -> None:
        """context-governor-audit.py should have --write-claim-ledger flag."""
        script = os.path.join(
            os.path.dirname(__file__), "..", "shared", "scripts", "context-governor-audit.py"
        )
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn("--write-claim-ledger", result.stdout)

    def test_benchmark_recall_has_write_claim_ledger(self) -> None:
        """benchmark-recall.py should have --write-claim-ledger flag."""
        script = os.path.join(
            os.path.dirname(__file__), "..", "shared", "scripts", "benchmark-recall.py"
        )
        if not os.path.exists(script):
            self.skipTest("benchmark-recall.py not yet created by subagent")
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn("--write-claim-ledger", result.stdout)


if __name__ == "__main__":
    unittest.main()