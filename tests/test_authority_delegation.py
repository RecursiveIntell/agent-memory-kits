#!/usr/bin/env python3
"""Unit tests for the authority-delegation lease system."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "shared", "scripts", "authority-delegation.py"
)


def run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT_PATH] + args,
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestAuthorityDelegation(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.store = os.path.join(self.tmpdir, "leases.jsonl")

    def test_create_lease(self) -> None:
        """Create a lease and verify schema, operator, delegate, capabilities, expires_at."""
        result = run_script([
            "create-lease",
            "--operator", "admin",
            "--delegate", "agent-alpha",
            "--capabilities", "reembed,vacuum",
            "--duration-mins", "30",
            "--store", self.store,
        ])
        self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")
        lease = json.loads(result.stdout.strip())
        self.assertEqual(lease["schema"], "AuthorityLeaseV1")
        self.assertEqual(lease["operator"], "admin")
        self.assertEqual(lease["delegate"], "agent-alpha")
        self.assertEqual(lease["capabilities"], ["reembed", "vacuum"])
        self.assertTrue(lease["lease_id"].startswith("lease:"))
        # Verify expires_at is ~30 mins after created_at
        created = datetime.strptime(lease["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        expires = datetime.strptime(lease["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        delta = expires - created
        self.assertEqual(delta, timedelta(minutes=30))
        # Verify it was appended to the store
        with open(self.store, "r") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        stored = json.loads(lines[0])
        self.assertEqual(stored["lease_id"], lease["lease_id"])

    def test_verify_lease_active(self) -> None:
        """Create a lease then verify it's active."""
        run_script([
            "create-lease",
            "--operator", "admin",
            "--delegate", "agent-beta",
            "--capabilities", "reembed,vacuum",
            "--duration-mins", "60",
            "--store", self.store,
        ])
        result = run_script([
            "verify-lease",
            "--delegate", "agent-beta",
            "--capability", "reembed",
            "--store", self.store,
        ])
        self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")
        out = json.loads(result.stdout.strip())
        self.assertTrue(out["valid"])
        self.assertEqual(out["reason"], "active lease found")

    def test_verify_lease_expired(self) -> None:
        """Create a lease with duration-mins=0 then verify it's rejected."""
        run_script([
            "create-lease",
            "--operator", "admin",
            "--delegate", "agent-gamma",
            "--capabilities", "reembed",
            "--duration-mins", "0",
            "--store", self.store,
        ])
        result = run_script([
            "verify-lease",
            "--delegate", "agent-gamma",
            "--capability", "reembed",
            "--store", self.store,
        ])
        self.assertEqual(result.returncode, 1, msg=f"stdout: {result.stdout}")
        out = json.loads(result.stdout.strip())
        self.assertFalse(out["valid"])

    def test_verify_lease_wrong_capability(self) -> None:
        """Create lease with 'reembed' but verify 'delete' → rejected."""
        run_script([
            "create-lease",
            "--operator", "admin",
            "--delegate", "agent-delta",
            "--capabilities", "reembed",
            "--duration-mins", "30",
            "--store", self.store,
        ])
        result = run_script([
            "verify-lease",
            "--delegate", "agent-delta",
            "--capability", "delete",
            "--store", self.store,
        ])
        self.assertEqual(result.returncode, 1, msg=f"stdout: {result.stdout}")
        out = json.loads(result.stdout.strip())
        self.assertFalse(out["valid"])

    def test_verify_lease_missing_store(self) -> None:
        """Verify with nonexistent store file → rejected."""
        missing_store = os.path.join(self.tmpdir, "nonexistent.jsonl")
        result = run_script([
            "verify-lease",
            "--delegate", "agent-epsilon",
            "--capability", "reembed",
            "--store", missing_store,
        ])
        self.assertEqual(result.returncode, 1, msg=f"stdout: {result.stdout}")
        out = json.loads(result.stdout.strip())
        self.assertFalse(out["valid"])


if __name__ == "__main__":
    unittest.main()