#!/usr/bin/env python3
"""RecursiveIntell Pro license client for shared/pro scripts.

This client intentionally keeps free-mode scripts usable by default while making
Pro enforcement explicit and receipt-visible when `RI_PRO_ENFORCE=1` is set.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

DEFAULT_SERVER = "https://license.recursiveintell.com"
DEFAULT_CACHE = Path.home() / ".ri-pro-license-token.json"
DEFAULT_CONFIG = Path.home() / ".ri-pro-config.json"
_TRUE = {"1", "true", "yes", "on"}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUE


def pro_enforcement_enabled() -> bool:
    return _truthy(os.environ.get("RI_PRO_ENFORCE"))


def machine_fingerprint() -> str:
    raw = f"{platform.node()}-{platform.machine()}-{platform.system()}-{socket.gethostname()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load_config() -> dict:
    config: dict = {}
    if DEFAULT_CONFIG.exists():
        try:
            config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            config = {}
    if key := os.environ.get("RI_PRO_LICENSE_KEY"):
        config["license_key"] = key
    if server := os.environ.get("RI_PRO_LICENSE_SERVER"):
        config["server"] = server
    if cache := os.environ.get("RI_PRO_LICENSE_CACHE"):
        config["cache"] = cache
    if _truthy(os.environ.get("RI_PRO_LICENSE_SKIP")):
        config["skip"] = True
    return config


def _parse_expires(token: dict) -> datetime | None:
    raw = token.get("expires_at")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def token_is_current(token: dict, *, buffer_secs: int = 0) -> bool:
    expires = _parse_expires(token)
    if not expires:
        return False
    remaining = (expires - datetime.now(timezone.utc)).total_seconds()
    return remaining > buffer_secs


def load_cached_token(cache_path: Path) -> dict | None:
    if not cache_path.exists():
        return None
    try:
        token = json.loads(cache_path.read_text(encoding="utf-8"))
        if token_is_current(token, buffer_secs=300):
            return token
    except Exception:
        return None
    return None


def save_cached_token(token: dict, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(token, indent=2), encoding="utf-8")
    try:
        cache_path.chmod(0o600)
    except Exception:
        pass


def verify_license(license_key: str, server: str, cache_path: Path, timeout: float = 10.0) -> dict | None:
    body = json.dumps({
        "license_key": license_key,
        "machine_fingerprint": machine_fingerprint(),
    }).encode("utf-8")
    req = request.Request(
        server.rstrip("/") + "/verify-license",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        token = result.get("token") if result.get("ok") else None
        if isinstance(token, dict) and token_is_current(token):
            save_cached_token(token, cache_path)
            return token
    except error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", str(exc))
        except Exception:
            msg = f"HTTP {exc.code}"
        print(f"License error: {msg}", file=sys.stderr)
    except Exception as exc:
        print(f"License server unreachable: {exc}", file=sys.stderr)
    return None


def get_token(required_features: list[str] | None = None) -> dict | None:
    config = load_config()
    if config.get("skip"):
        return None
    cache_path = Path(config.get("cache", str(DEFAULT_CACHE)))
    needed = set(required_features or [])

    token = load_cached_token(cache_path)
    if token and needed.issubset(set(token.get("features", []))):
        return token

    license_key = config.get("license_key")
    if not license_key:
        return None
    server = config.get("server", os.environ.get("RI_PRO_LICENSE_SERVER", DEFAULT_SERVER))
    token = verify_license(license_key, server, cache_path)
    if token and needed.issubset(set(token.get("features", []))):
        return token
    return None


def license_state_for_receipt(feature: str, *, enforce: bool | None = None) -> dict:
    """Return receipt-safe license state.

    `blocked=True` means a Pro-enforced script must not proceed.
    `skipped=True` is allowed only for explicit development mode and is not trusted
    by downstream production verifiers.
    """
    enforced = pro_enforcement_enabled() if enforce is None else bool(enforce)
    config = load_config()
    base = {
        "schema": "RecursiveIntellProLicenseStateV1",
        "feature": feature,
        "enforced": enforced,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    if config.get("skip"):
        return {
            **base,
            "trusted": False,
            "blocked": False,
            "skipped": True,
            "reason": "development skip",
            "token": None,
        }
    if not enforced:
        return {
            **base,
            "trusted": False,
            "blocked": False,
            "skipped": False,
            "reason": "not enforced",
            "token": None,
        }
    token = get_token([feature])
    if token:
        return {
            **base,
            "trusted": True,
            "blocked": False,
            "skipped": False,
            "reason": "valid token",
            "token": token,
        }
    return {
        **base,
        "trusted": False,
        "blocked": enforced,
        "skipped": False,
        "reason": "license unavailable",
        "token": None,
    }


def require_license_state(feature: str, *, enforce: bool | None = None) -> dict:
    state = license_state_for_receipt(feature, enforce=enforce)
    if state.get("blocked"):
        print(json.dumps({"ok": False, "error": "license required", "license_state": state}), file=sys.stderr)
        raise SystemExit(1)
    return state


def token_for_receipt(feature: str) -> dict | None:
    return license_state_for_receipt(feature).get("token")
