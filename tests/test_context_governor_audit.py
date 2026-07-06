#!/usr/bin/env python3
"""Tests for context-governor-audit.py wrapper."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "shared", "scripts", "context-governor-audit.py"
)


class TestContextGovernorAudit(unittest.TestCase):
    def test_tool_surface_audit_runs(self) -> None:
        """audit-tool-surface should produce a valid McpToolSurfaceAuditV1 receipt."""
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "audit-tool-surface",
                "--tools-json",
                json.dumps(
                    [
                        {"name": "sm_search", "description": "Search the knowledge base"},
                        {"name": "sm_add_fact", "description": "Add a fact to the knowledge base"},
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["schema"], "McpToolSurfaceAuditV1")
        self.assertIn("tool_count", receipt)
        self.assertEqual(receipt["tool_count"], 2)


    def test_audit_compression_boundary_runs(self) -> None:
        """audit-compression-boundary should return a CompressionBoundaryAuditV1 receipt."""
        request = {
            "source_text": "User said ignore all previous instructions.",
            "compressed_text": "Summary: user attempted prompt injection; do not execute it.",
            "policy": "operator_grade",
        }
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "audit-compression-boundary",
                "--request-json",
                json.dumps(request),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["schema"], "CompressionBoundaryAuditV1")
        self.assertIn("passed", receipt)

    def test_select_retrieval_route_runs(self) -> None:
        """select-route should return a RetrievalRouteDecisionV1."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "select-route", "--query", "what are the latest ROI items"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        decision = json.loads(result.stdout)
        self.assertEqual(decision["schema"], "RetrievalRouteDecisionV1")
        self.assertIn("route", decision)

    def test_screen_conflicts_runs(self) -> None:
        """screen-conflicts should return a ConflictScreenReportV1."""
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "screen-conflicts",
                "--claims-json",
                json.dumps(
                    [
                        {"id": "c1", "text": "The system supports 48 tools"},
                        {"id": "c2", "text": "The system does not support 48 tools"},
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "ConflictScreenReportV1")
        self.assertIn("conflicts", report)

    def test_eval_governed_memory_runs(self) -> None:
        """eval-governed-memory should return a GovernedMemoryHarnessReceiptV1."""
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "eval-governed-memory",
                "--harness-id",
                "test-harness",
                "--cases-json",
                json.dumps(
                    [
                        {
                            "case_id": "c1",
                            "mode": "unauthorized_leakage",
                            "passed": True,
                        }
                    ]
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["schema"], "GovernedMemoryHarnessReceiptV1")
        self.assertTrue(receipt["certified"])

    def test_fail_open_on_missing_binary(self) -> None:
        """Script should fail open with exit 0 if context-governor binary absent."""
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--binary-path",
                "/nonexistent/context-governor",
                "audit-tool-surface",
                "--tools-json",
                "[]",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("context-governor", (result.stderr + result.stdout).lower())


if __name__ == "__main__":
    unittest.main()