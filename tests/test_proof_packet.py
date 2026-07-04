#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/proof-packet.py"
spec = importlib.util.spec_from_file_location("proof_packet", SCRIPT)
assert spec and spec.loader
proof_packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof_packet)


class ProofPacketTests(unittest.TestCase):
    def write_json(self, directory: Path, name: str, payload: object) -> Path:
        path = directory / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_promote_packet_joins_command_claim_and_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = self.write_json(root, "cmd.json", {"command": "pytest", "returncode": 0})
            claim = self.write_json(root, "claim.json", {"claim": "tests passed"})
            disposition = self.write_json(root, "disp.json", {"disposition": "promote"})
            packet, promoted = proof_packet.build_packet([command], claim, disposition)
            self.assertTrue(promoted)
            self.assertTrue(packet["gate_promoted"])
            self.assertEqual(packet["schema"], proof_packet.SCHEMA)
            self.assertEqual(packet["command_receipts"][0]["json"]["command"], "pytest")
            self.assertRegex(packet["packet_sha256"], r"^[0-9a-f]{64}$")

    def test_reject_disposition_does_not_promote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = self.write_json(root, "cmd.json", {"passed": True})
            claim = self.write_json(root, "claim.json", {"claim": "done"})
            disposition = self.write_json(root, "disp.json", {"disposition": "reject"})
            packet, promoted = proof_packet.build_packet([command], claim, disposition)
            self.assertFalse(promoted)
            self.assertFalse(packet["gate_promoted"])

    def test_failed_command_does_not_promote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = self.write_json(root, "cmd.json", {"exit_code": 1})
            claim = self.write_json(root, "claim.json", {"claim": "done"})
            disposition = self.write_json(root, "disp.json", {"disposition": "promote"})
            packet, promoted = proof_packet.build_packet([command], claim, disposition)
            self.assertFalse(promoted)
            self.assertFalse(packet["commands_passed"])

    def test_unknown_command_status_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = self.write_json(root, "cmd.json", {"command": "pytest"})
            claim = self.write_json(root, "claim.json", {"claim": "done"})
            disposition = self.write_json(root, "disp.json", {"disposition": "promote"})
            packet, promoted = proof_packet.build_packet([command], claim, disposition)
            self.assertFalse(promoted)
            self.assertFalse(packet["commands_passed"])


if __name__ == "__main__":
    unittest.main()
