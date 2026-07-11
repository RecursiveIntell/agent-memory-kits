#!/usr/bin/env python3
"""Contract tests for the bounded live trust-kernel benchmark harness."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/benchmark-memory-trust-kernel.py"
FIXTURES = ROOT / "shared/fixtures/memory-trust-kernel.json"

spec = importlib.util.spec_from_file_location("memory_trust_kernel_bench", SCRIPT)
assert spec and spec.loader
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class MemoryTrustKernelBenchTests(unittest.TestCase):
    def test_fixed_fixture_covers_bounded_deterministic_suites(self) -> None:
        corpus = json.loads(FIXTURES.read_text(encoding="utf-8"))
        self.assertEqual(corpus["schema"], "MemoryTrustKernelFixturesV1")
        self.assertEqual({case["suite"] for case in corpus["cases"]}, {"state_validity", "pipeline", "poisoning"})
        self.assertTrue(any(case["expected"] == "rejected" for case in corpus["cases"] if case["suite"] == "poisoning"))

    def test_plan_gates_are_declared_before_any_execution(self) -> None:
        gates = bench.predeclared_gates()
        self.assertEqual(gates["state_validity"]["max_superseded_leakage"], 0.20)
        self.assertEqual(gates["pipeline"]["min_stage_specific_receipts"], 0.95)
        self.assertEqual(gates["poisoning"]["min_benign_retention"], 0.95)

    def test_stage_statuses_remain_distinct(self) -> None:
        cases = [
            {"name": "empty", "observed": "empty"},
            {"name": "skipped", "observed": "skipped"},
            {"name": "degraded", "observed": "degraded"},
            {"name": "failed", "observed": "failed"},
            {"name": "budget", "observed": "budget_exhausted"},
        ]
        self.assertEqual(bench.classify_pipeline_cases(cases), {case["name"]: case["observed"] for case in cases})

    def test_unsupported_capabilities_are_not_tested_not_passed(self) -> None:
        result = bench.not_tested("reasoning_drift", "no deterministic evaluator configured")
        self.assertEqual(result["status"], "not_tested")
        self.assertIn("reason", result)
        self.assertNotIn("passed", result)

    def test_cli_writes_machine_readable_bounded_report_without_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--fixtures", str(FIXTURES), "--endpoint", "http://127.0.0.1:59997", "--out", str(out)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "MemoryTrustKernelBenchmarkV1")
            self.assertEqual(report["execution"]["live_surface"], "unavailable")
            self.assertEqual(report["suites"]["reasoning_drift"]["status"], "not_tested")


if __name__ == "__main__":
    unittest.main(verbosity=2)
