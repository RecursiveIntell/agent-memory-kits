#!/usr/bin/env python3
"""Tests for forge-admin-mcp.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "shared", "scripts", "forge-admin-mcp.py"
)


class TestForgeAdminMcp(unittest.TestCase):
    def test_lists_tools(self) -> None:
        """forge-admin-mcp should list verify-patch and related tools."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--list-tools"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        tools = json.loads(result.stdout)
        tool_names = [t["name"] for t in tools]
        self.assertIn("forge_verify_patch", tool_names)
        self.assertIn("forge_get_attribution", tool_names)
        self.assertIn("forge_predict_risk", tool_names)
        self.assertIn("forge_export_evidence", tool_names)

    def test_tool_descriptions_have_admin_boundary(self) -> None:
        """Each tool description should mention admin-only status."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--list-tools"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        tools = json.loads(result.stdout)
        for tool in tools:
            self.assertIn(
                "ADMIN",
                tool["description"].upper(),
                f"Tool {tool['name']} missing ADMIN boundary in description",
            )

    def test_tool_descriptions_mention_patch_verification(self) -> None:
        """Tool descriptions should mention patch verification or release-gate."""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--list-tools"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        tools = json.loads(result.stdout)
        for tool in tools:
            desc_lower = tool["description"].lower()
            self.assertTrue(
                "patch" in desc_lower or "verification" in desc_lower or "release-gate" in desc_lower,
                f"Tool {tool['name']} description should mention patch/verification/release-gate",
            )

    def test_export_evidence_with_missing_receipt(self) -> None:
        """forge_export_evidence should return error for missing receipt."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "forge_admin_mcp", SCRIPT
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.handle_tool_call("forge_export_evidence", {"receipt_path": "/nonexistent"})
        self.assertIn("error", result)

    def test_export_evidence_with_valid_receipt(self) -> None:
        """forge_export_evidence should produce a bundle from a valid receipt."""
        import importlib.util
        import tempfile

        spec = importlib.util.spec_from_file_location(
            "forge_admin_mcp", SCRIPT
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "schema": "PatchVerificationReceiptV1",
                    "trace_id": "trace:forge-verify:abc123",
                    "claim": "tests pass",
                    "disposition": "promote",
                    "check_result": {"exit_code": 0},
                },
                f,
            )
            receipt_path = f.name

        try:
            result = mod.handle_tool_call("forge_export_evidence", {"receipt_path": receipt_path})
            self.assertTrue(result.get("ok"))
            bundle = result.get("bundle", {})
            self.assertEqual(bundle["schema"], "ForgeEvidenceBundleV1")
            self.assertEqual(bundle["claim"], "tests pass")
            self.assertEqual(bundle["disposition"], "promote")
        finally:
            os.unlink(receipt_path)


if __name__ == "__main__":
    unittest.main()