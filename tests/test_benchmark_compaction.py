#!/usr/bin/env python3
"""Unit tests for the cross-engine compaction benchmark."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure we can import the benchmark script
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "shared" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


class TestBenchmarkCompaction(unittest.TestCase):
    """Tests for benchmark-compaction-cross-engine.py."""

    def setUp(self) -> None:
        self.script_path = SCRIPTS_DIR / "benchmark-compaction-cross-engine.py"
        self.fixtures_dir = REPO_ROOT / "shared" / "fixtures"

    def _run_benchmark(self, out_path: str) -> dict:
        """Run the benchmark script and return the parsed JSON report."""
        result = subprocess.run(
            [
                sys.executable,
                str(self.script_path),
                "--fixtures-dir",
                str(self.fixtures_dir),
                "--out",
                out_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Benchmark failed with stderr: {result.stderr}\nstdout: {result.stdout}",
        )
        with open(out_path) as f:
            return json.load(f)

    def test_fails_open_on_missing_engines(self) -> None:
        """Should produce a report even if squeez is not installed."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            out_path = tmp.name

        try:
            report = self._run_benchmark(out_path)
            # Report must exist and have engines
            self.assertIn("engines", report)
            # squeez engine should be present (available=false is fine)
            self.assertIn("squeez", report["engines"])
            # The report should still be produced regardless of squeez availability
            self.assertIsInstance(report, dict)
            # head-tail should be available even if squeez isn't
            self.assertTrue(report["engines"]["head-tail"]["available"])
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_report_has_schema(self) -> None:
        """Output should have CompactionBenchmarkV1 schema."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            out_path = tmp.name

        try:
            report = self._run_benchmark(out_path)
            self.assertEqual(report["schema"], "CompactionBenchmarkV1")
            self.assertIn("timestamp", report)
            self.assertIn("machine_fingerprint", report)
            self.assertIn("engines", report)
            self.assertIn("per_fixture", report)
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_head_tail_works(self) -> None:
        """head-tail engine should always be available and produce a compression ratio."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            out_path = tmp.name

        try:
            report = self._run_benchmark(out_path)
            ht = report["engines"]["head-tail"]
            self.assertTrue(ht["available"], "head-tail should always be available")
            self.assertGreater(
                ht["compression_ratio"],
                0,
                "head-tail should produce a compression ratio > 0",
            )
            self.assertGreater(ht["token_before"], 0)
            self.assertGreaterEqual(ht["token_after"], 0)
            self.assertTrue(
                ht["token_after"] < ht["token_before"],
                "head-tail should reduce token count",
            )
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()