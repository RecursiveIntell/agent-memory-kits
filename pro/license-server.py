#!/usr/bin/env python3
"""license-server.py — RecursiveIntell Pro license verification server.

Issues HMAC-SHA256 signed tokens bound to license key + machine fingerprint.
Tokens have short TTL and are embedded in every pro receipt.

Endpoints:
  POST /verify-license   — verify license key, issue signed token
  POST /validate-token   — validate a previously issued token
  GET  /health           — health check

Token payload (base64url-encoded JSON):
  - license_key_hash: SHA-256 of license key
  - machine_fingerprint: caller-provided fingerprint
  - issued_at: ISO timestamp
  - expires_at: ISO timestamp (TTL configurable, default 1 hour)
  - features: list of enabled feature strings
  - signature: HMAC-SHA256(payload, server_secret)

The server secret is read from LICENSE_SERVER_SECRET env var or a file.
Never share the secret. The client only has the public verification key
(a different key pair would be better, but HMAC with server-side secret is
simpler and sufficient for this use case).

Usage:
  LICENSE_SERVER_SECRET="your-secret" python license-server.py --port 8443
  LICENSE_SERVER_SECRET_FILE=/path/to/secret python license-server.py --port 8443
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- License database (in production: SQLite or external DB) ---
# For now, licenses are stored in a JSON file. Replace with real DB later.
LICENSE_DB_PATH = os.environ.get("LICENSE_DB_PATH", "licenses.json")


def load_licenses() -> dict:
    if os.path.exists(LICENSE_DB_PATH):
        with open(LICENSE_DB_PATH) as f:
            return json.load(f)
    return {}


def save_licenses(db: dict) -> None:
    with open(LICENSE_DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


def get_server_secret() -> bytes:
    secret = os.environ.get("LICENSE_SERVER_SECRET")
    if not secret:
        secret_file = os.environ.get("LICENSE_SERVER_SECRET_FILE")
        if secret_file and os.path.exists(secret_file):
            with open(secret_file) as f:
                secret = f.read().strip()
    if not secret:
        raise RuntimeError("LICENSE_SERVER_SECRET or LICENSE_SERVER_SECRET_FILE must be set")
    return secret.encode("utf-8")


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sign_token(payload: dict, secret: bytes) -> str:
    """Sign payload with HMAC-SHA256, return base64url(signature)."""
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(secret, payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig


def create_token(license_key: str, machine_fingerprint: str, features: list[str], ttl_seconds: int, secret: bytes) -> dict:
    now = datetime.now(timezone.utc)
    expires = datetime.fromtimestamp(now.timestamp() + ttl_seconds, timezone.utc)
    payload = {
        "license_key_hash": sha256_hex(license_key),
        "machine_fingerprint": machine_fingerprint,
        "issued_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "features": features,
        "token_id": uuid.uuid4().hex[:16],
    }
    payload["signature"] = sign_token(payload, secret)
    return payload


def validate_token(token: dict, secret: bytes) -> tuple[bool, str]:
    """Validate a token. Returns (valid, reason)."""
    if "signature" not in token:
        return False, "missing signature"
    sig = token["signature"]
    payload_copy = {k: v for k, v in token.items() if k != "signature"}
    expected_sig = sign_token(payload_copy, secret)
    if not hmac.compare_digest(sig, expected_sig):
        return False, "invalid signature"
    expires_at_str = token.get("expires_at", "")
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.now(timezone.utc) > expires_at:
            return False, "token expired"
    except Exception:
        return False, "invalid expires_at"
    return True, "valid"


class LicenseHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True, "server": "license-server", "time": datetime.now(timezone.utc).isoformat()})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            secret = get_server_secret()
        except RuntimeError as e:
            self._send_json(500, {"error": str(e)})
            return

        if self.path == "/verify-license":
            body = self._read_body()
            license_key = body.get("license_key", "")
            machine_fingerprint = body.get("machine_fingerprint", "")
            if not license_key or not machine_fingerprint:
                self._send_json(400, {"error": "license_key and machine_fingerprint required"})
                return

            db = load_licenses()
            record = db.get(sha256_hex(license_key))
            if not record:
                self._send_json(403, {"error": "invalid license key"})
                return

            if record.get("status") != "active":
                self._send_json(403, {"error": f"license {record.get('status', 'unknown')}"})
                return

            # Check machine fingerprint if license is locked
            locked_fp = record.get("machine_fingerprint")
            if locked_fp and locked_fp != machine_fingerprint:
                self._send_json(403, {"error": "machine fingerprint mismatch"})
                return

            # Auto-lock to first machine if not locked
            if not locked_fp:
                record["machine_fingerprint"] = machine_fingerprint
                db[sha256_hex(license_key)] = record
                save_licenses(db)

            features = record.get("features", [
                "evidence-workbench", "claim-ledger", "admin-preflight",
                "authority-delegation", "forge-admin", "context-governor-audit",
                "benchmark-recall", "release-gate", "agent-guard",
            ])
            ttl = int(record.get("ttl_seconds", 3600))

            token = create_token(license_key, machine_fingerprint, features, ttl, secret)
            self._send_json(200, {"ok": True, "token": token})

        elif self.path == "/validate-token":
            body = self._read_body()
            token = body.get("token", {})
            if not token:
                self._send_json(400, {"error": "token required"})
                return
            valid, reason = validate_token(token, secret)
            if valid:
                self._send_json(200, {"ok": True, "valid": True, "features": token.get("features", [])})
            else:
                self._send_json(403, {"ok": False, "valid": False, "reason": reason})

        elif self.path == "/create-license":
            # Admin endpoint — in production, protect with admin token
            body = self._read_body()
            admin_secret = body.get("admin_secret", "")
            if admin_secret != os.environ.get("LICENSE_ADMIN_SECRET", "change-me"):
                self._send_json(403, {"error": "admin secret required"})
                return
            license_key = f"RI-PRO-{uuid.uuid4().hex[:20].upper()}"
            customer = body.get("customer", "unknown")
            ttl = int(body.get("ttl_seconds", 3600))
            db = load_licenses()
            db[sha256_hex(license_key)] = {
                "license_key": license_key,
                "customer": customer,
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": ttl,
                "features": body.get("features", [
                    "evidence-workbench", "claim-ledger", "admin-preflight",
                    "authority-delegation", "forge-admin", "context-governor-audit",
                    "benchmark-recall", "release-gate", "agent-guard",
                ]),
            }
            save_licenses(db)
            self._send_json(200, {"ok": True, "license_key": license_key})

        elif self.path == "/revoke-license":
            body = self._read_body()
            admin_secret = body.get("admin_secret", "")
            if admin_secret != os.environ.get("LICENSE_ADMIN_SECRET", "change-me"):
                self._send_json(403, {"error": "admin secret required"})
                return
            license_key = body.get("license_key", "")
            db = load_licenses()
            key_hash = sha256_hex(license_key)
            if key_hash in db:
                db[key_hash]["status"] = "revoked"
                db[key_hash]["revoked_at"] = datetime.now(timezone.utc).isoformat()
                save_licenses(db)
                self._send_json(200, {"ok": True, "revoked": license_key})
            else:
                self._send_json(404, {"error": "license not found"})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:
        # Suppress default logging — add structured logging in production
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="RecursiveIntell Pro license server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LICENSE_SERVER_PORT", "8443")))
    parser.add_argument("--host", default=os.environ.get("LICENSE_SERVER_HOST", "127.0.0.1"))
    args = parser.parse_args()

    # Ensure secret is available
    try:
        get_server_secret()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=__import__("sys").stderr)
        raise SystemExit(1)

    server = HTTPServer((args.host, args.port), LicenseHandler)
    print(f"License server running on {args.host}:{args.port}")
    print(f"License DB: {LICENSE_DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()