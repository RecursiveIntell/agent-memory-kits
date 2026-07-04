"""Unit tests for the admin action preflight system."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

# Load the hyphenated module name via importlib.
SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "shared", "scripts")
SCRIPT_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "admin-preflight.py"))
_spec = importlib.util.spec_from_file_location("admin_preflight", SCRIPT_PATH)
admin_preflight = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(admin_preflight)


class PreflightTests(unittest.TestCase):
    """Tests for the preflight subcommand."""

    def _run_preflight(self, args: list[str]) -> tuple[int, dict]:
        """Run preflight and return (exit_code, parsed_json)."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = admin_preflight.main(["preflight"] + args)
        output = buf.getvalue().strip()
        data = json.loads(output)
        return rc, data

    def test_emits_effect_intent_for_reembed(self):
        """preflight for reembed_missing emits EffectIntentV1 with risk_level=low."""
        rc, data = self._run_preflight([
            "--operation", "reembed_missing",
            "--target", "general",
            "--operator", "tester",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(data["schema"], "EffectIntentV1")
        self.assertEqual(data["operation"], "reembed_missing")
        self.assertEqual(data["risk_level"], "low")
        self.assertIn("timestamp", data)

    def test_emits_effect_intent_for_delete(self):
        """preflight for delete_namespace emits EffectIntentV1 with risk_level=critical."""
        rc, data = self._run_preflight([
            "--operation", "delete_namespace",
            "--target", "general",
            "--operator", "tester",
            "--confirm",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(data["schema"], "EffectIntentV1")
        self.assertEqual(data["operation"], "delete_namespace")
        self.assertEqual(data["risk_level"], "critical")

    def test_blocks_destructive_without_confirmation(self):
        """delete_namespace without --confirm exits 1 and has blocked=true."""
        rc, data = self._run_preflight([
            "--operation", "delete_namespace",
            "--target", "general",
            "--operator", "tester",
        ])
        self.assertEqual(rc, 1)
        self.assertTrue(data.get("blocked"))
        self.assertIn("confirmation required", data.get("reason", ""))

    def test_allows_destructive_with_confirmation(self):
        """delete_namespace with --confirm exits 0."""
        rc, data = self._run_preflight([
            "--operation", "delete_namespace",
            "--target", "general",
            "--operator", "tester",
            "--confirm",
        ])
        self.assertEqual(rc, 0)
        self.assertFalse(data.get("blocked"))
        self.assertEqual(data["schema"], "EffectIntentV1")
        self.assertTrue(data["confirmed"])


class PostflightTests(unittest.TestCase):
    """Tests for the postflight subcommand."""

    def test_postflight_emits_execution_receipt(self):
        """postflight emits EffectExecutionReceiptV1 with exit_code."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = admin_preflight.main([
                "postflight",
                "--operation", "reembed_missing",
                "--target", "general",
                "--exit-code", "0",
                "--duration-secs", "3.5",
            ])
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(rc, 0)
        self.assertEqual(data["schema"], "EffectExecutionReceiptV1")
        self.assertEqual(data["operation"], "reembed_missing")
        self.assertEqual(data["exit_code"], 0)
        self.assertEqual(data["duration_secs"], 3.5)
        self.assertIn("timestamp", data)

    def test_postflight_without_duration(self):
        """postflight works without --duration-secs (defaults to None)."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = admin_preflight.main([
                "postflight",
                "--operation", "vacuum",
                "--target", "general",
                "--exit-code", "1",
            ])
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(rc, 0)
        self.assertIsNone(data["duration_secs"])
        self.assertEqual(data["exit_code"], 1)


class VerifyReceiptTests(unittest.TestCase):
    """Tests for the verify-receipt subcommand."""

    VALID_RECEIPT = json.dumps({
        "schema": "EffectIntentV1",
        "operation": "delete_namespace",
        "target": "general",
        "operator": "tester",
        "risk_level": "critical",
        "confirmed": True,
        "timestamp": "2026-07-03T00:00:00Z",
    })

    def _run_verify(self, receipt_json: str) -> tuple[int, dict]:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = admin_preflight.main([
                "verify-receipt",
                "--receipt-json", receipt_json,
            ])
        data = json.loads(buf.getvalue().strip())
        return rc, data

    def test_verify_receipt_accepts_valid(self):
        """A valid receipt passes verification."""
        rc, data = self._run_verify(self.VALID_RECEIPT)
        self.assertEqual(rc, 0)
        self.assertTrue(data.get("valid"))

    def test_verify_receipt_rejects_missing(self):
        """An empty / {} receipt fails verification."""
        rc, data = self._run_verify(json.dumps({}))
        self.assertEqual(rc, 1)
        self.assertFalse(data.get("valid"))

    def test_verify_receipt_rejects_wrong_schema(self):
        """A receipt with the wrong schema fails."""
        rc, data = self._run_verify(json.dumps({
            "schema": "SomethingElse",
            "operation": "vacuum",
            "target": "general",
            "operator": "tester",
            "risk_level": "low",
        }))
        self.assertEqual(rc, 1)
        self.assertFalse(data.get("valid"))

    def test_verify_receipt_rejects_invalid_json(self):
        """Invalid JSON fails verification."""
        rc, data = self._run_verify("not-json-at-all")
        self.assertEqual(rc, 1)
        self.assertFalse(data.get("valid"))


class RiskLevelTests(unittest.TestCase):
    """Additional tests for risk-level mapping and medium-risk confirm behaviour."""

    def test_medium_risk_does_not_require_confirm(self):
        """import_envelope (medium) does not require --confirm."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = admin_preflight.main([
                "preflight",
                "--operation", "import_envelope",
                "--target", "/tmp/envelope.json",
                "--operator", "tester",
            ])
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(rc, 0)
        self.assertEqual(data["schema"], "EffectIntentV1")
        self.assertEqual(data["risk_level"], "medium")

    def test_high_risk_requires_confirm(self):
        """reembed_all (high) requires --confirm."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = admin_preflight.main([
                "preflight",
                "--operation", "reembed_all",
                "--target", "general",
                "--operator", "tester",
            ])
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(rc, 1)
        self.assertTrue(data.get("blocked"))

    def test_high_risk_allowed_with_confirm(self):
        """reembed_all (high) with --confirm exits 0."""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = admin_preflight.main([
                "preflight",
                "--operation", "reembed_all",
                "--target", "general",
                "--operator", "tester",
                "--confirm",
            ])
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(rc, 0)
        self.assertEqual(data["risk_level"], "high")
        self.assertTrue(data["confirmed"])


if __name__ == "__main__":
    unittest.main()