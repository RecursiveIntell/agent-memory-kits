#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRO_DIR = ROOT / "pro"
SCRIPT_DIR = ROOT / "shared" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pro_license_client_exports_shared_enforcement_api() -> None:
    mod = load_module("pro_license_client_hardening", PRO_DIR / "license_client.py")
    assert hasattr(mod, "require_license_state")
    assert hasattr(mod, "license_state_for_receipt")


def test_pro_manifest_references_existing_packaged_assets() -> None:
    manifest = json.loads((PRO_DIR / "plugin.json").read_text(encoding="utf-8"))
    hermes = manifest["hermes"]
    missing: list[str] = []
    for skill in hermes.get("skills", []):
        rel = Path("skills") / skill / "SKILL.md"
        if not (PRO_DIR / rel).exists():
            missing.append(str(rel))
    for command_path in hermes.get("commands", {}).values():
        if not (PRO_DIR / command_path).exists():
            missing.append(command_path)
    for server in hermes.get("mcp_servers", {}).values():
        for arg in server.get("args", []):
            if isinstance(arg, str) and arg.startswith("scripts/") and not (PRO_DIR / arg).exists():
                missing.append(arg)
    assert missing == []


def test_license_server_without_admin_secret_does_not_accept_change_me() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["LICENSE_SERVER_SECRET"] = "test-secret"
        env["LICENSE_DB_PATH"] = str(Path(tmpdir) / "licenses.json")
        env.pop("LICENSE_ADMIN_SECRET", None)
        proc = subprocess.Popen(
            [sys.executable, str(PRO_DIR / "license-server.py"), "--host", "127.0.0.1", "--port", "18766"],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen("http://127.0.0.1:18766/health", timeout=0.2).read()
                    break
                except Exception:
                    time.sleep(0.1)
            body = json.dumps({"admin_secret": "change-me", "customer": "attacker"}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:18766/create-license",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=2)
                assert False, "default admin secret unexpectedly created a license"
            except urllib.error.HTTPError as exc:
                assert exc.code in {403, 503}
            assert not Path(env["LICENSE_DB_PATH"]).exists()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_release_gate_quarantines_high_risk_when_proof_debt_store_errors() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_store = Path(tmpdir) / "directory-not-jsonl"
        bad_store.mkdir()
        out = Path(tmpdir) / "out"
        env = os.environ.copy()
        env["RI_PROOF_DEBT_STORE"] = str(bad_store)
        env["RI_PRO_LICENSE_SKIP"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "release-gate-v2.py"),
                "--claim",
                "high risk proof-debt errors must not promote",
                "--cmd",
                "true",
                "--cwd",
                tmpdir,
                "--risk-class",
                "high",
                "--out-dir",
                str(out),
                "--no-memory",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert result.returncode != 0
        packets = sorted(out.glob("*.json"))
        assert packets, result.stderr
        packet = json.loads(packets[0].read_text(encoding="utf-8"))
        assert packet["disposition"] == "quarantine"
        assert "proof_debt_error" in packet


def test_verify_patch_uses_configured_semantic_memory_url() -> None:
    mod = load_module("verify_patch_hardening", SCRIPT_DIR / "verify-patch.py")
    source = (SCRIPT_DIR / "verify-patch.py").read_text(encoding="utf-8")
    assert "http://localhost:8082/add" not in source
    assert hasattr(mod, "_semantic_memory_base_url")
