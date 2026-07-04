#!/usr/bin/env python3
"""Tests for memory-gaps.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "shared", "scripts", "memory-gaps.py")


class TestMemoryGaps(unittest.TestCase):
    def test_fails_open_on_missing_server(self) -> None:
        """Should produce a gap report with server_available=false if server is down."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--domain", "test", "--out", "/tmp/test-gaps.json"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "SEMANTIC_MEMORY_HTTP_PORT": "19999"},
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        with open("/tmp/test-gaps.json") as f:
            report = json.load(f)
        self.assertEqual(report["schema"], "GapReportV1")
        self.assertFalse(report["server_available"])
        self.assertIn("trace_id", report)

    def test_report_has_correct_schema(self) -> None:
        """Gap report should have GapReportV1 schema and required fields."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--domain", "test",
             "--out", "/tmp/test-gaps-schema.json"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "SEMANTIC_MEMORY_HTTP_PORT": "19999"},
        )
        with open("/tmp/test-gaps-schema.json") as f:
            report = json.load(f)
        self.assertEqual(report["schema"], "GapReportV1")
        self.assertIn("gaps", report)
        self.assertIn("summary", report)
        self.assertIn("timestamp", report)
        self.assertIn("server_available", report)

    def test_stdout_output(self) -> None:
        """Without --out, should print JSON to stdout."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--domain", "test"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "SEMANTIC_MEMORY_HTTP_PORT": "19999"},
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "GapReportV1")


if __name__ == "__main__":
    unittest.main()