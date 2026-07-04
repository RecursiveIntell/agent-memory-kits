#!/usr/bin/env python3
"""Tests for the receipt-bench-style recall benchmark script."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/benchmark-recall.py"

# Load the benchmark module for direct imports
spec = importlib.util.spec_from_file_location("benchmark_recall", SCRIPT)
assert spec and spec.loader
benchmark_recall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark_recall)


class BenchmarkRecallTests(unittest.TestCase):
    def test_fails_open_on_missing_fixtures(self) -> None:
        """--fixtures-dir /nonexistent should exit 1 with 'fixtures' in stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "receipt.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixtures-dir",
                    "/nonexistent/path/that/does/not/exist",
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 1, f"Expected exit 1, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}")
            self.assertIn("fixtures", result.stderr.lower())

    def test_fails_open_on_missing_server(self) -> None:
        """If fixtures exist but server is down, should emit a receipt with server_available=false and exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            fixtures_dir = Path(tmp) / "fixtures"
            fixtures_dir.mkdir()
            fixture_file = fixtures_dir / "test.jsonl"
            fixture_file.write_text(
                json.dumps({
                    "query": "test query for missing server",
                    "expected_result_ids": ["fact:00000000-0000-0000-0000-000000000001"],
                    "top_k": 5,
                }) + "\n",
                encoding="utf-8",
            )
            out_path = Path(tmp) / "receipt.json"

            # Use a port that's almost certainly not running a server
            env = os.environ.copy()
            env["SEMANTIC_MEMORY_HTTP_PORT"] = "59999"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixtures-dir",
                    str(fixtures_dir),
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertTrue(out_path.exists(), "Receipt file should have been created")
            receipt = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertFalse(
                receipt["server_available"],
                "server_available should be false when server is down",
            )
            self.assertGreater(receipt["fixtures_used"], 0)

    def test_receipt_schema(self) -> None:
        """If a receipt is produced, it has the right schema field."""
        with tempfile.TemporaryDirectory() as tmp:
            fixtures_dir = Path(tmp) / "fixtures"
            fixtures_dir.mkdir()
            fixture_file = fixtures_dir / "schema-test.jsonl"
            fixture_file.write_text(
                json.dumps({
                    "query": "schema validation test query",
                    "expected_result_ids": ["fact:00000000-0000-0000-0000-000000000010"],
                    "top_k": 3,
                }) + "\n",
                encoding="utf-8",
            )
            out_path = Path(tmp) / "receipt.json"

            env = os.environ.copy()
            env["SEMANTIC_MEMORY_HTTP_PORT"] = "59998"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixtures-dir",
                    str(fixtures_dir),
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            self.assertEqual(result.returncode, 0)
            self.assertTrue(out_path.exists())
            receipt = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["schema"], "SMBenchmarkReport")
            # Verify all required fields are present
            required_fields = {
                "schema", "timestamp", "git_commit", "machine_fingerprint",
                "fixtures_used", "server_available", "recall_at_k",
                "ndcg_at_k", "mrr", "per_fixture",
            }
            for field in required_fields:
                self.assertIn(field, receipt, f"Missing required field: {field}")
            # Verify per_fixture entries have the right sub-fields
            self.assertIsInstance(receipt["per_fixture"], list)
            self.assertGreater(len(receipt["per_fixture"]), 0)
            pf = receipt["per_fixture"][0]
            for field in ("query", "recall", "ndcg", "mrr", "results_count"):
                self.assertIn(field, pf, f"Missing per_fixture field: {field}")


if __name__ == "__main__":
    unittest.main(verbosity=2)