#!/usr/bin/env python3
"""Focused contract tests for the diagnostic memory-influence receipt."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/benchmark-diagnostic-memory.py"
FIXTURES = ROOT / "shared/fixtures/memory-influence-fixtures.json"
FIXTURE_SCHEMA = ROOT / "shared/fixtures/schemas/memory-influence-fixture.schema.json"
RECEIPT_SCHEMA = ROOT / "shared/fixtures/schemas/memory-influence-receipt.schema.json"

spec = importlib.util.spec_from_file_location("diagnostic_memory_benchmark", SCRIPT)
assert spec and spec.loader
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class MemoryInfluenceTests(unittest.TestCase):
    def test_cc0_fixture_and_schemas_publish_the_receipt_contract(self) -> None:
        fixture = json.loads(FIXTURES.read_text(encoding="utf-8"))
        self.assertEqual(fixture["license"], "CC0-1.0")
        self.assertEqual(json.loads(FIXTURE_SCHEMA.read_text(encoding="utf-8"))["title"], "Memory Influence Fixture Bundle")
        self.assertEqual(json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))["title"], "Memory Influence Receipt")

    def test_offline_receipt_covers_causal_cells_and_deterministic_metrics(self) -> None:
        receipt = benchmark.build_memory_influence_receipt(FIXTURES, mode="offline")

        self.assertEqual(receipt["schema"], "MemoryInfluenceReceiptV1")
        self.assertEqual(receipt["execution"]["inference_calls"], 0)
        self.assertEqual(
            receipt["cells"],
            [
                "no_memory",
                "gold_memory",
                "retrieved_memory",
                "unlabeled_memory",
                "witnessed_state_labeled_memory",
                "distractors",
                "poison",
                "governed_admission",
            ],
        )
        measured = receipt["cases"]["fresh-config"]
        self.assertEqual(measured["status"], "measured")
        self.assertGreater(measured["metrics"]["answer_quality_delta"]["gold_memory"], 0)
        self.assertLess(measured["metrics"]["unsupported_claim_delta"]["governed_admission"], 0)
        self.assertTrue(measured["metrics"]["citation_support"]["witnessed_state_labeled_memory"]["supported"])
        self.assertTrue(measured["metrics"]["tool_selection_delta"]["gold_memory"]["matches_expected"])
        self.assertTrue(measured["metrics"]["tool_argument_delta"]["gold_memory"]["matches_expected"])

    def test_risk_triggered_mode_skips_untriggered_cases_and_preserves_not_tested(self) -> None:
        receipt = benchmark.build_memory_influence_receipt(FIXTURES, mode="risk_triggered")

        self.assertEqual(receipt["cases"]["fresh-config"]["status"], "not_tested")
        self.assertEqual(receipt["cases"]["fresh-config"]["reason"], "risk trigger was not met")
        self.assertEqual(receipt["cases"]["poisoned-tool"]["status"], "measured")
        self.assertEqual(receipt["cases"]["unlabeled-query"]["status"], "not_tested")
        self.assertEqual(receipt["cases"]["unlabeled-query"]["reason"], "no deterministic evaluator exists")

    def test_diagnostic_cli_embeds_the_influence_receipt(self) -> None:
        # The extension must be part of the existing diagnostic receipt, not a parallel report.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "diagnostic.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--memory-influence-fixtures",
                    str(FIXTURES),
                    "--memory-influence-mode",
                    "risk_triggered",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["memory_influence"]["schema"], "MemoryInfluenceReceiptV1")
        self.assertEqual(report["memory_influence"]["execution"]["mode"], "risk_triggered")


if __name__ == "__main__":
    unittest.main(verbosity=2)
