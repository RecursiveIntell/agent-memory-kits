#!/usr/bin/env python3
"""Tests for release-gate-v2.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "shared", "scripts", "release-gate-v2.py"
)


class TestReleaseGateV2(unittest.TestCase):
    def _env(self, tmpdir: str) -> dict:
        env = os.environ.copy()
        env["RI_PROOF_DEBT_STORE"] = os.path.join(tmpdir, "proof-debt.jsonl")
        return env

    def test_produces_proof_packet_with_disposition(self) -> None:
        """release-gate-v2 should emit a proof packet with adjudication disposition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--claim",
                    "Focused tests pass",
                    "--cmd",
                    "true",
                    "--cwd",
                    "/tmp",
                    "--out-dir",
                    tmpdir,
                    "--no-memory",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._env(tmpdir),
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            packets = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
            self.assertTrue(len(packets) > 0, "No proof packet emitted")
            with open(os.path.join(tmpdir, packets[0])) as f:
                packet = json.load(f)
            self.assertEqual(packet["schema"], "ReleaseGateProofPacketV1")
            self.assertEqual(packet["disposition"], "promote")
            self.assertIn("command_receipts", packet)
            self.assertIn("claim", packet)
            self.assertIn("trace_id", packet)
            self.assertIn("case_id", packet)
            self.assertIn("packet_sha256", packet)
            self.assertIn("git_commit", packet)

    def test_rejects_on_failing_command(self) -> None:
        """release-gate-v2 should reject when a command fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--claim",
                    "This should fail",
                    "--cmd",
                    "false",
                    "--cwd",
                    "/tmp",
                    "--out-dir",
                    tmpdir,
                    "--no-memory",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._env(tmpdir),
            )
            self.assertNotEqual(result.returncode, 0)
            packets = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
            self.assertTrue(len(packets) > 0)
            with open(os.path.join(tmpdir, packets[0])) as f:
                packet = json.load(f)
            self.assertEqual(packet["disposition"], "reject")

    def test_quarantine_on_timeout(self) -> None:
        """release-gate-v2 should quarantine when a command times out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--claim",
                    "This will timeout",
                    "--cmd",
                    "sleep 100",
                    "--cwd",
                    "/tmp",
                    "--timeout",
                    "2",
                    "--out-dir",
                    tmpdir,
                    "--no-memory",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._env(tmpdir),
            )
            self.assertNotEqual(result.returncode, 0)
            packets = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
            if packets:
                with open(os.path.join(tmpdir, packets[0])) as f:
                    packet = json.load(f)
                self.assertEqual(packet["disposition"], "quarantine")

    def test_multiple_commands_all_pass(self) -> None:
        """release-gate-v2 should promote when all commands pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--claim",
                    "Multiple gates pass",
                    "--cmd",
                    "true",
                    "--cmd",
                    "echo hello",
                    "--cwd",
                    "/tmp",
                    "--out-dir",
                    tmpdir,
                    "--no-memory",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._env(tmpdir),
            )
            self.assertEqual(result.returncode, 0)
            packets = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
            with open(os.path.join(tmpdir, packets[0])) as f:
                packet = json.load(f)
            self.assertEqual(packet["disposition"], "promote")
            self.assertEqual(len(packet["command_receipts"]), 2)

    def test_has_write_claim_ledger_flag(self) -> None:
        """release-gate-v2 should have --write-claim-ledger flag."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn("--write-claim-ledger", result.stdout)


if __name__ == "__main__":
    unittest.main()