#!/usr/bin/env python3
"""From Plan: Phase 1 — hook HTTP auth helpers talk to token-gated warm servers."""
from __future__ import annotations

import http.server
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOLVE = ROOT / "claude/plugins/semantic-memory/hooks/_resolve.sh"


class _AuthedHandler(http.server.BaseHTTPRequestHandler):
    token = "test-hook-token"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _ok(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {self.token}":
            self.send_response(401)
            self.end_headers()
            return
        if self.path == "/health":
            self._ok(b'{"ok":true,"service":"semantic-memory-mcp"}')
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {self.token}":
            self.send_response(401)
            self.end_headers()
            return
        if self.path == "/search":
            self._ok(b'{"ok":true,"results":[{"result_id":"fact:1","content":"hit","namespace":"infrastructure","score":0.03}]}')
            return
        self.send_response(404)
        self.end_headers()


def _serve() -> tuple[http.server.HTTPServer, str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _AuthedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def _bash(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **env}
    return subprocess.run(
        ["bash", "-c", script],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
        env=merged,
        cwd=str(ROOT),
    )


class HookHttpAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.base = _serve()
        cls.port = cls.base.rsplit(":", 1)[-1]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def _source(self) -> str:
        return f'. "{RESOLVE}" && sm_resolve && SM_HTTP="{self.base}" && SM_HTTP_PORT="{self.port}"'

    def test_sm_warm_fails_without_token(self) -> None:
        """From Plan: unauthenticated /health against a token-gated server is not warm."""
        env = {
            "SEMANTIC_MEMORY_MCP_BIN": "/bin/true",
            "SEMANTIC_MEMORY_HTTP_PORT": self.port,
        }
        env.pop("SEMANTIC_MEMORY_HTTP_TOKEN", None)
        env.pop("SEMANTIC_MEMORY_HTTP_TOKEN_FILE", None)
        proc = _bash(
            self._source() + "; sm_warm; echo EXIT:$?",
            env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("EXIT:1", proc.stdout)

    def test_sm_warm_succeeds_with_token_file(self) -> None:
        """From Plan: SEMANTIC_MEMORY_HTTP_TOKEN_FILE is sent as Bearer on /health."""
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write("test-hook-token\n")
            path = fh.name
        os.chmod(path, 0o600)
        try:
            proc = _bash(
                self._source() + "; sm_warm; echo EXIT:$?",
                {
                    "SEMANTIC_MEMORY_MCP_BIN": "/bin/true",
                    "SEMANTIC_MEMORY_HTTP_PORT": self.port,
                    "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": path,
                },
            )
        finally:
            os.unlink(path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("EXIT:0", proc.stdout)

    def test_sm_warm_succeeds_with_canonical_auth_token_file(self) -> None:
        """The canonical launcher auth-token-file name must work for hook warm checks."""
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write("test-hook-token\n")
            path = fh.name
        os.chmod(path, 0o600)
        try:
            proc = _bash(
                self._source() + "; sm_warm; echo EXIT:$?",
                {
                    "SEMANTIC_MEMORY_MCP_BIN": "/bin/true",
                    "SEMANTIC_MEMORY_HTTP_PORT": self.port,
                    "SEMANTIC_MEMORY_HTTP_AUTH_TOKEN_FILE": path,
                },
            )
        finally:
            os.unlink(path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("EXIT:0", proc.stdout)

    def test_sm_curl_search_sends_bearer(self) -> None:
        """From Plan: sm_curl POST /search includes the Bearer token."""
        proc = _bash(
            self._source()
            + '; sm_curl -fsS -m 2 -X POST "$SM_HTTP/search" -H "content-type: application/json" -d \'{"query":"x","top_k":1}\'',
            {
                "SEMANTIC_MEMORY_MCP_BIN": "/bin/true",
                "SEMANTIC_MEMORY_HTTP_PORT": self.port,
                "SEMANTIC_MEMORY_HTTP_TOKEN": "test-hook-token",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"ok":true', proc.stdout)


if __name__ == "__main__":
    unittest.main()
