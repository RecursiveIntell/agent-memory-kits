#!/usr/bin/env python3
"""Tests for license_client.py and license-server.py integration."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PRO_DIR = Path(__file__).resolve().parents[1] / "pro"
sys.path.insert(0, str(PRO_DIR))

from license_client import machine_fingerprint, load_config, load_cached_token, token_for_receipt

# Import server-side functions for testing
import importlib.util as _ilu
_server_spec = _ilu.spec_from_file_location("license_server", PRO_DIR / "license-server.py")
if _server_spec and _server_spec.loader:
    _server_mod = _ilu.module_from_spec(_server_spec)
    sys.modules["license_server"] = _server_mod
    _server_spec.loader.exec_module(_server_mod)
    sign_token = _server_mod.sign_token
    validate_token = _server_mod.validate_token

import hashlib


class TestLicenseClient(unittest.TestCase):
    def test_machine_fingerprint_stable(self) -> None:
        """Machine fingerprint should be stable across calls in same session."""
        fp1 = machine_fingerprint()
        fp2 = machine_fingerprint()
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 32)

    def test_load_config_env_override(self) -> None:
        """Env vars should override config file."""
        os.environ["RI_PRO_LICENSE_KEY"] = "RI-PRO-TEST123"
        os.environ["RI_PRO_LICENSE_SERVER"] = "http://localhost:9999"
        config = load_config()
        self.assertEqual(config.get("license_key"), "RI-PRO-TEST123")
        self.assertEqual(config.get("server"), "http://localhost:9999")
        del os.environ["RI_PRO_LICENSE_KEY"]
        del os.environ["RI_PRO_LICENSE_SERVER"]

    def test_skip_mode_returns_null_token(self) -> None:
        """RI_PRO_LICENSE_SKIP=1 should return skipped token (development mode)."""
        os.environ["RI_PRO_LICENSE_SKIP"] = "1"
        sys.path.insert(0, str(PRO_DIR))
        from license_client import token_for_receipt
        token = token_for_receipt("release-gate")
        # In skip mode, token is a dict with skipped=True (not None, but marked as skipped)
        if token is not None:
            self.assertTrue(token.get("skipped"))
        else:
            self.assertIsNone(token)  # acceptable — null token in skip mode
        del os.environ["RI_PRO_LICENSE_SKIP"]

    def test_token_sign_and_validate(self) -> None:
        """Token should validate with correct secret, fail with wrong secret."""
        secret = b"test-secret-key"
        payload = {
            "license_key_hash": hashlib.sha256(b"RI-PRO-TEST").hexdigest(),
            "machine_fingerprint": "abc123",
            "issued_at": "2026-07-04T00:00:00+00:00",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "features": ["release-gate"],
            "token_id": "abc123",
        }
        payload["signature"] = sign_token(payload, secret)
        valid, reason = validate_token(payload, secret)
        self.assertTrue(valid, f"should be valid: {reason}")

        # Wrong secret
        valid, reason = validate_token(payload, b"wrong-secret")
        self.assertFalse(valid)
        self.assertEqual(reason, "invalid signature")

    def test_expired_token_rejected(self) -> None:
        """Expired token should be rejected."""
        secret = b"test-secret-key"
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        payload = {
            "license_key_hash": "abc",
            "machine_fingerprint": "xyz",
            "issued_at": "2026-07-04T00:00:00+00:00",
            "expires_at": past,
            "features": [],
            "token_id": "test",
        }
        payload["signature"] = sign_token(payload, secret)
        valid, reason = validate_token(payload, secret)
        self.assertFalse(valid)
        self.assertEqual(reason, "token expired")

    def test_cached_token_roundtrip(self) -> None:
        """Cached token should survive save and load."""
        from datetime import datetime, timezone, timedelta
        secret = b"test-secret-key"
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        token = {
            "license_key_hash": "abc",
            "machine_fingerprint": "xyz",
            "issued_at": "2026-07-04T00:00:00+00:00",
            "expires_at": future,
            "features": ["release-gate"],
            "token_id": "test123",
            "signature": "fake-sig",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(token, f)
            cache_path = Path(f.name)
        try:
            loaded = load_cached_token(cache_path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["token_id"], "test123")
        finally:
            cache_path.unlink(missing_ok=True)


class TestLicenseServer(unittest.TestCase):
    """Test the license server with a running instance."""

    @classmethod
    def setUpClass(cls) -> None:
        """Start a test license server."""
        cls.secret = "test-server-secret-12345"
        cls.db_path = tempfile.mktemp(suffix=".json")
        cls.port = 18443
        env = os.environ.copy()
        env["LICENSE_SERVER_SECRET"] = cls.secret
        env["LICENSE_DB_PATH"] = cls.db_path
        env["LICENSE_ADMIN_SECRET"] = "admin-test-secret"
        cls.proc = subprocess.Popen(
            [sys.executable, str(PRO_DIR / "license-server.py"),
             "--port", str(cls.port), "--host", "127.0.0.1"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(1)  # wait for server to start

    @classmethod
    def tearDownClass(cls) -> None:
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        if os.path.exists(cls.db_path):
            os.unlink(cls.db_path)

    def test_health_check(self) -> None:
        """Server should respond to /health."""
        from urllib import request
        resp = request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(data["ok"])

    def test_create_and_verify_license(self) -> None:
        """Create a license, then verify it to get a token."""
        from urllib import request
        # Create license
        body = json.dumps({
            "admin_secret": "admin-test-secret",
            "customer": "test-customer",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/create-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(result["ok"])
        license_key = result["license_key"]
        self.assertTrue(license_key.startswith("RI-PRO-"))

        # Verify license
        body = json.dumps({
            "license_key": license_key,
            "machine_fingerprint": "test-fp-123",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/verify-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(result["ok"])
        token = result["token"]
        self.assertIn("signature", token)
        self.assertIn("features", token)
        self.assertIn("release-gate", token["features"])

        # Validate token
        body = json.dumps({"token": token}).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/validate-token",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(result["valid"])

    def test_invalid_license_rejected(self) -> None:
        """Invalid license key should be rejected."""
        from urllib import request, error
        body = json.dumps({
            "license_key": "RI-PRO-INVALID",
            "machine_fingerprint": "test-fp",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/verify-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            request.urlopen(req, timeout=5)
            self.fail("Should have raised HTTPError")
        except error.HTTPError as e:
            self.assertEqual(e.code, 403)

    def test_machine_fingerprint_locking(self) -> None:
        """License should auto-lock to first machine fingerprint."""
        from urllib import request
        # Create license
        body = json.dumps({
            "admin_secret": "admin-test-secret",
            "customer": "lock-test",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/create-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = request.urlopen(req, timeout=5)
        license_key = json.loads(resp.read().decode("utf-8"))["license_key"]

        # Verify from machine A
        body = json.dumps({
            "license_key": license_key,
            "machine_fingerprint": "machine-A",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/verify-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = request.urlopen(req, timeout=5)
        self.assertTrue(json.loads(resp.read().decode("utf-8"))["ok"])

        # Verify from machine B (should fail — locked to A)
        from urllib import request, error
        body = json.dumps({
            "license_key": license_key,
            "machine_fingerprint": "machine-B",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/verify-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            request.urlopen(req, timeout=5)
            self.fail("Should have raised HTTPError — machine fingerprint mismatch")
        except error.HTTPError as e:
            self.assertEqual(e.code, 403)

    def test_revoke_license(self) -> None:
        """Revoked license should be rejected."""
        from urllib import request, error
        # Create license
        body = json.dumps({
            "admin_secret": "admin-test-secret",
            "customer": "revoke-test",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/create-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = request.urlopen(req, timeout=5)
        license_key = json.loads(resp.read().decode("utf-8"))["license_key"]

        # Revoke
        body = json.dumps({
            "admin_secret": "admin-test-secret",
            "license_key": license_key,
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/revoke-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = request.urlopen(req, timeout=5)
        self.assertTrue(json.loads(resp.read().decode("utf-8"))["ok"])

        # Verify — should fail
        body = json.dumps({
            "license_key": license_key,
            "machine_fingerprint": "revoke-test-fp",
        }).encode()
        req = request.Request(
            f"http://127.0.0.1:{self.port}/verify-license",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            request.urlopen(req, timeout=5)
            self.fail("Should have raised HTTPError — license revoked")
        except error.HTTPError as e:
            self.assertEqual(e.code, 403)


if __name__ == "__main__":
    unittest.main()