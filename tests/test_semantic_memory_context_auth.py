#!/usr/bin/env python3
"""From Plan: Phase 1 — semantic-memory-context.py sends Bearer on warm HTTP."""
from __future__ import annotations

import http.server
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/semantic-memory-context.py"


def _load():
    spec = importlib.util.spec_from_file_location("sm_context", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _AuthedHandler(http.server.BaseHTTPRequestHandler):
    token = "ctx-token"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        auth = self.headers.get("Authorization", "")
        length = int(self.headers.get("Content-Length") or 0)
        _ = self.rfile.read(length)
        if auth != f"Bearer {self.token}":
            self.send_response(401)
            self.end_headers()
            return
        body = json.dumps({"ok": True, "results": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ContextAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _load()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _AuthedHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        host, port = self.server.server_address[:2]
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_http_post_without_token_returns_none(self) -> None:
        os.environ["SEMANTIC_MEMORY_HTTP_URL"] = self.base
        os.environ.pop("SEMANTIC_MEMORY_HTTP_TOKEN", None)
        os.environ.pop("SEMANTIC_MEMORY_HTTP_TOKEN_FILE", None)
        self.assertIsNone(self.mod.http_post("/search", {"query": "x", "top_k": 1}))

    def test_http_post_with_auth_token_file_succeeds(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write("ctx-token\n")
            path = fh.name
        os.chmod(path, 0o600)
        try:
            os.environ["SEMANTIC_MEMORY_HTTP_URL"] = self.base
            os.environ.pop("SEMANTIC_MEMORY_HTTP_TOKEN", None)
            os.environ["SEMANTIC_MEMORY_HTTP_AUTH_TOKEN_FILE"] = path
            result = self.mod.http_post("/search", {"query": "x", "top_k": 1})
        finally:
            os.unlink(path)
            os.environ.pop("SEMANTIC_MEMORY_HTTP_AUTH_TOKEN_FILE", None)
            os.environ.pop("SEMANTIC_MEMORY_HTTP_URL", None)
        self.assertEqual(result, {"ok": True, "results": []})


if __name__ == "__main__":
    unittest.main()
