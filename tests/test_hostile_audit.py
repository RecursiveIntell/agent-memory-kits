#!/usr/bin/env python3
"""Unit tests for hostile-audit.py — verifies fail-open behaviour, schema, and trace IDs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "shared", "scripts", "hostile-audit.py")
SCRIPT = os.path.abspath(SCRIPT)

FACT_JSON = json.dumps({"content": "The Eiffel Tower is in Paris."})


def _run_audit(*extra_args: str) -> tuple[int, str, str]:
    """Run hostile-audit.py with the given args and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, SCRIPT, "--fact-json", FACT_JSON] + list(extra_args)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


class TestHostileAudit(unittest.TestCase):
    def test_fails_open_on_missing_auditor(self) -> None:
        """When the auditor URL is unreachable, exit 0 with valid=null."""
        rc, stdout, stderr = _run_audit("--auditor-url", "http://localhost:19999")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}. stderr:\n{stderr}")
        data = json.loads(stdout.strip())
        self.assertIsNone(data["valid"], f"Expected valid=null, got {data['valid']}")
        self.assertEqual(data["reason"], "auditor unavailable")

    def test_emits_correct_schema(self) -> None:
        """Output should have schema=HostileAuditResultV1 and all required fields."""
        rc, stdout, stderr = _run_audit("--auditor-url", "http://localhost:19999")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}. stderr:\n{stderr}")
        data = json.loads(stdout.strip())
        self.assertEqual(data["schema"], "HostileAuditResultV1")
        for field in ("schema", "fact_id", "auditor_model", "valid", "reason", "timestamp", "trace_id"):
            self.assertIn(field, data, f"Missing required field: {field}")

    def test_trace_id_present(self) -> None:
        """Output trace_id should start with 'trace:hostile-audit:'."""
        rc, stdout, stderr = _run_audit("--auditor-url", "http://localhost:19999")
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}. stderr:\n{stderr}")
        data = json.loads(stdout.strip())
        self.assertTrue(
            data["trace_id"].startswith("trace:hostile-audit:"),
            f"trace_id does not start with 'trace:hostile-audit:': {data['trace_id']}",
        )


if __name__ == "__main__":
    unittest.main()