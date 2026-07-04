#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "shared" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestLicenseEnforcement(unittest.TestCase):
    def setUp(self) -> None:
        self.old_env = dict(os.environ)
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "token.json"
        os.environ.pop("RI_PRO_LICENSE_KEY", None)
        os.environ.pop("RI_PRO_LICENSE_SKIP", None)
        os.environ["RI_PRO_LICENSE_CACHE"] = str(self.cache)
        os.environ["RI_PRO_LICENSE_SERVER"] = "http://127.0.0.1:9"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()

    def _write_token(self, *, expires_delta_secs: int = 3600, features: list[str] | None = None) -> None:
        token = {
            "token_id": "tok:test",
            "license_key_hash": "hash",
            "machine_fingerprint": "fp",
            "features": features or ["forge-admin", "release-gate", "admin-preflight", "authority-delegation", "agent-guard"],
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_delta_secs)).isoformat(),
            "signature": "test-signature",
        }
        self.cache.write_text(json.dumps(token), encoding="utf-8")

    def test_missing_license_blocks_when_enforced(self) -> None:
        os.environ["RI_PRO_ENFORCE"] = "1"
        mod = load_module("license_client_shared_missing", SCRIPT_DIR / "license_client.py")
        state = mod.license_state_for_receipt("forge-admin")
        self.assertFalse(state["trusted"])
        self.assertTrue(state["blocked"])
        self.assertEqual(state["reason"], "license unavailable")

    def test_skip_mode_is_untrusted_but_not_blocked_for_dev(self) -> None:
        os.environ["RI_PRO_ENFORCE"] = "1"
        os.environ["RI_PRO_LICENSE_SKIP"] = "1"
        mod = load_module("license_client_shared_skip", SCRIPT_DIR / "license_client.py")
        state = mod.license_state_for_receipt("forge-admin")
        self.assertFalse(state["trusted"])
        self.assertFalse(state["blocked"])
        self.assertTrue(state["skipped"])

    def test_cached_valid_token_is_trusted(self) -> None:
        os.environ["RI_PRO_ENFORCE"] = "1"
        self._write_token()
        mod = load_module("license_client_shared_valid", SCRIPT_DIR / "license_client.py")
        state = mod.license_state_for_receipt("forge-admin")
        self.assertTrue(state["trusted"])
        self.assertFalse(state["blocked"])
        self.assertEqual(state["token"]["token_id"], "tok:test")

    def test_cached_expired_token_blocks_when_enforced(self) -> None:
        os.environ["RI_PRO_ENFORCE"] = "1"
        self._write_token(expires_delta_secs=-60)
        mod = load_module("license_client_shared_expired", SCRIPT_DIR / "license_client.py")
        state = mod.license_state_for_receipt("forge-admin")
        self.assertFalse(state["trusted"])
        self.assertTrue(state["blocked"])

    def test_verify_patch_embeds_license_state(self) -> None:
        os.environ["RI_PRO_ENFORCE"] = "1"
        os.environ["RI_PRO_LICENSE_SKIP"] = "1"
        repo = Path(self.tmp.name) / "repo"
        out = Path(self.tmp.name) / "out"
        repo.mkdir()
        (repo / "file.txt").write_text("ok", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "verify-patch.py"),
                "--repo", str(repo),
                "--claim", "license state smoke",
                "--check-cmd", "python -c 'print(123)'",
                "--out-dir", str(out),
                "--no-memory",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        receipt = json.loads(Path(data["receipt"]).read_text(encoding="utf-8"))
        self.assertIn("license_state", receipt)
        self.assertTrue(receipt["license_state"]["skipped"])
        self.assertFalse(receipt["license_state"]["trusted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
