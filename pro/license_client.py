#!/usr/bin/env python3
"""license_client.py — RecursiveIntell Pro license verification client.

This module is woven into every pro script. It contacts the license server,
gets a signed token, and embeds the token in every receipt the script emits.

Design principles:
  1. Every pro receipt includes a license_token field. Downstream tools
     (release-gate, doctor deep, claim-ledger) validate the token before
     trusting the receipt. Removing the license check invalidates the
     receipt chain that other tools depend on.
  2. The token is short-lived (default 1 hour). Scripts re-verify on each
     invocation. Caching is per-session only.
  3. The server URL and license key are set via env vars or config file.
     They are NOT in the source code. Removing the check means downstream
     tools reject the receipts.
  4. Machine fingerprinting binds the license to one machine, making
     sharing keys across machines require re-activation.
  5. The client never has the server secret. It only has the public-facing
     endpoints. The signature is verified server-side.

Env vars:
  RI_PRO_LICENSE_KEY      — the license key (RI-PRO-XXXX...)
  RI_PRO_LICENSE_SERVER   — server URL (default https://license.recursiveintell.com)
  RI_PRO_LICENSE_CACHE    — cache file path (default ~/.ri-pro-license-token.json)
  RI_PRO_LICENSE_SKIP     — if set to "1", skip verification (for development only;
                            receipts will have license_token=null and downstream
                            tools will reject them)

Config file (optional):
  ~/.ri-pro-config.json — {"license_key": "...", "server": "...", "skip": false}
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

DEFAULT_SERVER = os.environ.get("RI_PRO_LICENSE_SERVER", "https://license.recursiveintell.com")
DEFAULT_CACHE = Path.home() / ".ri-pro-license-token.json"
DEFAULT_CONFIG = Path.home() / ".ri-pro-config.json"

# Features list — must match what the server issues
PRO_FEATURES = [
    "evidence-workbench",
    "claim-ledger",
    "admin-preflight",
    "authority-delegation",
    "forge-admin",
    "context-governor-audit",
    "benchmark-recall",
    "release-gate",
]


def machine_fingerprint() -> str:
    """Generate a stable machine fingerprint."""
    raw = f"{platform.node()}-{platform.machine()}-{platform.system()}-{socket.gethostname()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load_config() -> dict:
    """Load license config from env vars or config file."""
    config = {}
    # Config file first
    if DEFAULT_CONFIG.exists():
        try:
            with open(DEFAULT_CONFIG) as f:
                config = json.load(f)
        except Exception:
            pass
    # Env vars override
    if key := os.environ.get("RI_PRO_LICENSE_KEY"):
        config["license_key"] = key
    if server := os.environ.get("RI_PRO_LICENSE_SERVER"):
        config["server"] = server
    if cache := os.environ.get("RI_PRO_LICENSE_CACHE"):
        config["cache"] = cache
    if os.environ.get("RI_PRO_LICENSE_SKIP", "").lower() in ("1", "true", "yes"):
        config["skip"] = True
    return config


def load_cached_token(cache_path: Path) -> dict | None:
    """Load a cached token if still valid."""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path) as f:
            token = json.load(f)
        expires_at = datetime.fromisoformat(token.get("expires_at", ""))
        if datetime.now(timezone.utc) < expires_at:
            # Still valid (with 5 min buffer)
            buffer_secs = 300
            remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
            if remaining > buffer_secs:
                return token
    except Exception:
        pass
    return None


def save_cached_token(token: dict, cache_path: Path) -> None:
    """Save token to cache file."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(token, f, indent=2)
        # Restrict permissions
        cache_path.chmod(0o600)
    except Exception:
        pass


def verify_license(license_key: str, server: str = DEFAULT_SERVER, cache_path: Path = DEFAULT_CACHE, timeout: float = 10.0) -> dict | None:
    """Contact the license server and get a signed token."""
    fp = machine_fingerprint()
    body = json.dumps({
        "license_key": license_key,
        "machine_fingerprint": fp,
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
            if result.get("ok") and result.get("token"):
                save_cached_token(result["token"], cache_path)
                return result["token"]
    except error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            print(f"License error: {err_body.get('error', str(e))}", file=sys.stderr)
        except Exception:
            print(f"License error: HTTP {e.code}", file=sys.stderr)
    except Exception as e:
        print(f"License server unreachable: {e}", file=sys.stderr)
    return None


def get_token(required_features: list[str] | None = None) -> dict | None:
    """Get a valid license token. Returns None if verification fails or is skipped."""
    config = load_config()

    if config.get("skip"):
        # Development mode — returns a null token. Downstream tools reject these.
        return None

    license_key = config.get("license_key")
    if not license_key:
        print("RI_PRO_LICENSE_KEY not set. Pro features require a license.", file=sys.stderr)
        print("Contact sales@recursiveintell.com for a license key.", file=sys.stderr)
        return None

    server = config.get("server", DEFAULT_SERVER)
    cache_path = Path(config.get("cache", str(DEFAULT_CACHE)))

    # Try cached token first
    token = load_cached_token(cache_path)
    if token:
        # Check required features
        token_features = set(token.get("features", []))
        needed = set(required_features or [])
        if needed.issubset(token_features):
            return token
        # Token doesn't have needed features — re-verify
        # (license may have been upgraded)

    # Contact server
    token = verify_license(license_key, server, cache_path)
    if token:
        token_features = set(token.get("features", []))
        needed = set(required_features or [])
        if needed and not needed.issubset(token_features):
            missing = needed - token_features
            print(f"License does not include required features: {missing}", file=sys.stderr)
            return None
    return token


def require_license(feature: str) -> dict:
    """Decorator-like guard for pro scripts. Returns a token dict or exits.

    Usage at the top of a pro script:
        from license_client import require_license
        token = require_license("release-gate")
        if not token:
            raise SystemExit(1)
        # ... rest of script, embed token in receipt ...
    """
    token = get_token([feature])
    if not token:
        print(f"License verification failed for feature: {feature}", file=sys.stderr)
        print("Set RI_PRO_LICENSE_KEY or configure ~/.ri-pro-config.json", file=sys.stderr)
        sys.exit(1)
    return token


def token_for_receipt(feature: str) -> dict | None:
    """Get a token suitable for embedding in a receipt.

    Returns None if license is skipped (development mode).
    Receipts with null tokens are rejected by downstream tools.
    """
    config = load_config()
    if config.get("skip"):
        return {"skipped": True, "reason": "development mode", "token_id": None}
    return get_token([feature])