#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import stat
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT.parent / "shared" / "scripts"
sys.path.insert(0, str(SHARED))

try:
    from license_client import require_license_state, load_config  # type: ignore
except Exception as exc:  # pragma: no cover
    require_license_state = None  # type: ignore
    load_config = None  # type: ignore
    IMPORT_ERROR = str(exc)
else:
    IMPORT_ERROR = None

REQUIRED_FILES = [
    ROOT / "plugin.json",
    ROOT / "scripts" / "forge-admin-mcp.py",
    ROOT / "scripts" / "agent-guard-mcp.py",
    ROOT / "scripts" / "claim-ledger-mcp.py",
]


def file_mode(path: Path) -> str | None:
    try:
        return oct(stat.S_IMODE(path.stat().st_mode))
    except FileNotFoundError:
        return None


def health_check(url: str) -> dict:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": resp.status == 200, "status": resp.status, "body": body[:500]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    checks: list[dict] = []
    ok = True

    cfg_path = Path(os.environ.get("RI_PRO_CONFIG", str(Path.home() / ".ri-pro-config.json")))
    cfg_mode = file_mode(cfg_path)
    cfg_exists = cfg_path.exists()
    cfg_perm_ok = cfg_mode in ("0o600", "0o400") if cfg_mode else False
    checks.append({
        "name": "config_file",
        "ok": cfg_exists and cfg_perm_ok,
        "path": str(cfg_path),
        "mode": cfg_mode,
        "reason": None if cfg_exists and cfg_perm_ok else "missing or permissions not 0600/0400",
    })
    ok = ok and cfg_exists and cfg_perm_ok

    if IMPORT_ERROR:
        checks.append({"name": "license_client_import", "ok": False, "error": IMPORT_ERROR})
        ok = False
        cfg = {}
    else:
        checks.append({"name": "license_client_import", "ok": True})
        cfg = load_config() if load_config else {}

    server_url = cfg.get("server_url") or os.environ.get("RI_PRO_LICENSE_URL") or ""
    if server_url:
        hc = health_check(server_url)
        checks.append({"name": "license_server_health", **hc, "url": server_url})
        ok = ok and bool(hc.get("ok"))
    else:
        checks.append({"name": "license_server_health", "ok": False, "reason": "server_url not configured"})
        ok = False

    if require_license_state:
        state = require_license_state("pro-doctor", enforce=False)
        checks.append({
            "name": "license_state",
            "ok": bool(state.get("trusted")),
            "trusted": state.get("trusted"),
            "skipped": state.get("skipped"),
            "reason": state.get("reason"),
            "token_id": state.get("token_id"),
        })
        ok = ok and bool(state.get("trusted"))

    for path in REQUIRED_FILES:
        exists = path.exists()
        checks.append({"name": "required_file", "ok": exists, "path": str(path)})
        ok = ok and exists

    receipt = {
        "schema": "RIProDoctorReceiptV1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": ok,
        "checks": checks,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
