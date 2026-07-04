#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/evidence-workbench.py"
spec = importlib.util.spec_from_file_location("evidence_workbench", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class EvidenceWorkbenchTests(unittest.TestCase):
    def test_run_command_receipt_captures_exit_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt = module.run_command("printf hello", Path(tmp), 10)
            self.assertEqual(receipt["exit_code"], 0)
            self.assertFalse(receipt["timed_out"])
            self.assertRegex(receipt["stdout_sha256"], r"^[0-9a-f]{64}$")
            self.assertIn("hello", receipt["stdout_preview"])

    def test_main_emits_promoted_packet_for_passing_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "receipts"
            argv = ["--claim", "plugin gates pass", "--cmd", "true", "--cwd", tmp, "--out-dir", str(out), "--no-memory"]
            with mock.patch.object(sys, "argv", [str(SCRIPT), *argv]):
                self.assertEqual(module.main(), 0)
            packets = list(out.glob("evidence-workbench-*.json"))
            self.assertEqual(len(packets), 1)
            packet = json.loads(packets[0].read_text(encoding="utf-8"))
            self.assertEqual(packet["disposition"], "promote")
            self.assertEqual(packet["claim"], "plugin gates pass")
            self.assertRegex(packet["proof_packet_sha256"], r"^[0-9a-f]{64}$")

    def test_main_rejects_failed_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "receipts"
            argv = ["--claim", "plugin gates pass", "--cmd", "false", "--cwd", tmp, "--out-dir", str(out), "--no-memory"]
            with mock.patch.object(sys, "argv", [str(SCRIPT), *argv]):
                self.assertEqual(module.main(), 1)
            packet = json.loads(next(out.glob("evidence-workbench-*.json")).read_text(encoding="utf-8"))
            self.assertEqual(packet["disposition"], "reject")
            self.assertEqual(packet["commands"][0]["exit_code"], 1)


if __name__ == "__main__":
    unittest.main()
