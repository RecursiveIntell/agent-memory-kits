#!/usr/bin/env python3
"""Focused coverage for Hermes semantic-memory HTTP authentication."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


PLUGIN_DIR = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN_DIR / "hooks"
RUN_SERVER = PLUGIN_DIR / "scripts" / "run-server.sh"
BENCHMARK = PLUGIN_DIR / "scripts" / "benchmark-retrieval.py"

sys.path.insert(0, str(PLUGIN_DIR))
import http_auth

spec = importlib.util.spec_from_file_location("hermes_hooks_common", HOOKS / "common.py")
assert spec and spec.loader
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


class _Handler(BaseHTTPRequestHandler):
    headers_seen: list[str | None] = []
    redirect_target: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        self._reply()

    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self._reply()

    def _reply(self) -> None:
        self.headers_seen.append(self.headers.get("Authorization"))
        if self.path == "/redirect" and self.redirect_target:
            self.send_response(302)
            self.send_header("Location", self.redirect_target)
            self.end_headers()
            return
        payload = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


class HermesHttpAuthTests(unittest.TestCase):
    def test_explicit_token_precedes_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "token"
            token_file.write_text("file-token\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {
                "SEMANTIC_MEMORY_HTTP_TOKEN": "  explicit-token \n",
                "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": str(token_file),
            }, clear=False):
                self.assertEqual(http_auth.resolve_http_token(), "explicit-token")

    def test_default_token_file_is_used_when_environment_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / ".hermes" / "semantic-memory-http-1739.token"
            token_file.parent.mkdir()
            token_file.write_text("default-file-token\n", encoding="utf-8")
            env = os.environ | {"HOME": tmp}
            env.pop("SEMANTIC_MEMORY_HTTP_TOKEN", None)
            env.pop("SEMANTIC_MEMORY_HTTP_TOKEN_FILE", None)
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(http_auth.resolve_http_token(), "default-file-token")

    def test_empty_explicit_token_falls_back_to_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "token"
            token_file.write_text("file-token\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {
                "SEMANTIC_MEMORY_HTTP_TOKEN": "",
                "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": str(token_file),
            }, clear=True):
                self.assertEqual(http_auth.resolve_http_token(), "file-token")

    def test_multiline_token_is_rejected_consistently(self) -> None:
        with mock.patch.dict(os.environ, {"SEMANTIC_MEMORY_HTTP_TOKEN": "first\nsecond"}, clear=True):
            self.assertIsNone(http_auth.resolve_http_token())

    def test_explicit_token_file_precedes_default_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            default_file = Path(tmp) / ".hermes" / "semantic-memory-http-1739.token"
            default_file.parent.mkdir()
            default_file.write_text("default-token\n", encoding="utf-8")
            explicit_file = Path(tmp) / "explicit-token"
            explicit_file.write_text("explicit-file-token\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {
                "HOME": tmp,
                "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": str(explicit_file),
            }, clear=True):
                self.assertEqual(http_auth.resolve_http_token(), "explicit-file-token")

    def test_http_helpers_fail_closed_without_sending_request(self) -> None:
        _Handler.headers_seen = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {
                "HOME": tmp,
                "SEMANTIC_MEMORY_HTTP_URL": f"http://127.0.0.1:{server.server_port}",
            }, clear=True):
                self.assertIsNone(common.http_get("/health"))
                self.assertIsNone(common.http_post("/search", {"query": "memory"}))
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(_Handler.headers_seen, [])

    def test_plaintext_non_loopback_url_is_rejected_before_open(self) -> None:
        with mock.patch.dict(os.environ, {
            "SEMANTIC_MEMORY_HTTP_URL": "http://example.com:1739",
            "SEMANTIC_MEMORY_HTTP_TOKEN": "header-token",
        }, clear=False), mock.patch.object(common._HTTP_OPENER, "open") as open_request:
            self.assertIsNone(common.http_get("/health"))
            open_request.assert_not_called()

    def test_malformed_http_urls_fail_closed_for_get_and_post(self) -> None:
        malformed = [
            "http://[::1",
            "http://127.0.0.1:bad",
            "http://127.0.0.1:70000",
            "https://",
            "https:///path",
            "http://:1739",
        ]
        for url in malformed:
            with self.subTest(url=url), mock.patch.dict(os.environ, {
                "SEMANTIC_MEMORY_HTTP_URL": url,
                "SEMANTIC_MEMORY_HTTP_TOKEN": "header-token",
            }, clear=False), mock.patch.object(common._HTTP_OPENER, "open") as open_request:
                self.assertIsNone(common.http_base())
                self.assertIsNone(common.http_get("/health"))
                self.assertIsNone(common.http_post("/search", {"query": "memory"}))
                open_request.assert_not_called()

    def test_redirect_is_not_followed_with_authorization(self) -> None:
        _Handler.headers_seen = []
        target = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        source = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        _Handler.redirect_target = f"http://127.0.0.1:{target.server_port}/target"
        threads = [
            threading.Thread(target=target.serve_forever, daemon=True),
            threading.Thread(target=source.serve_forever, daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            with mock.patch.dict(os.environ, {
                "SEMANTIC_MEMORY_HTTP_URL": f"http://127.0.0.1:{source.server_port}",
                "SEMANTIC_MEMORY_HTTP_TOKEN": "redirect-token",
            }, clear=False):
                self.assertIsNone(common.http_get("/redirect"))
        finally:
            _Handler.redirect_target = None
            source.shutdown()
            target.shutdown()
            source.server_close()
            target.server_close()
        self.assertEqual(_Handler.headers_seen, ["Bearer redirect-token"])

    def test_hook_get_and_post_emit_bearer_header(self) -> None:
        _Handler.headers_seen = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.dict(os.environ, {
                "SEMANTIC_MEMORY_HTTP_URL": f"http://127.0.0.1:{server.server_port}",
                "SEMANTIC_MEMORY_HTTP_TOKEN": "header-token",
            }, clear=False):
                self.assertEqual(common.http_get("/health"), {"ok": True})
                self.assertEqual(common.http_post("/search", {"query": "memory"}), {"ok": True})
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(_Handler.headers_seen, ["Bearer header-token", "Bearer header-token"])

    def test_stdio_launcher_does_not_require_a_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "semantic-memory-mcp"
            fake.write_text("#!/usr/bin/env bash\nif [ \"$1\" = \"--help\" ]; then echo '--tool-profile --http-port --http-auth-token'; else printf '%s\\n' \"$@\"; fi\n", encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ | {"HOME": tmp, "SEMANTIC_MEMORY_MCP_BIN": str(fake), "SEMANTIC_MEMORY_HTTP_PORT": "0"}
            env.pop("SEMANTIC_MEMORY_HTTP_TOKEN", None)
            env.pop("SEMANTIC_MEMORY_HTTP_TOKEN_FILE", None)
            proc = subprocess.run(["bash", str(RUN_SERVER)], text=True, capture_output=True, env=env, check=False)
            direct_secret = "forbidden-argv-secret"
            direct = subprocess.run(
                ["bash", str(RUN_SERVER), "--http-auth-token", direct_secret],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("--http-port", proc.stdout)
        self.assertNotIn("--http-auth-token", proc.stdout)
        self.assertEqual(direct.returncode, 2)
        self.assertNotIn(direct_secret, direct.stdout + direct.stderr)

    def test_http_launcher_matches_empty_fallback_and_edge_trimming_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "semantic-memory-mcp"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "if [ \"$1\" = \"--help\" ]; then printf '%s|%s' \"${SEMANTIC_MEMORY_HTTP_TOKEN-unset}\" \"${SM_BENCH_HTTP_AUTH_TOKEN-unset}\" > \"$CAPTURE_HELP_ENV\"; echo '--http-port --http-auth-token-file'; exit 0; fi\n"
                "printf 'ENV=%s|%s\\n' \"${SEMANTIC_MEMORY_HTTP_TOKEN-unset}\" \"${SM_BENCH_HTTP_AUTH_TOKEN-unset}\"\n"
                "printf '%s\\n' \"$@\"\n"
                "while [ \"$#\" -gt 0 ]; do "
                "if [ \"$1\" = \"--http-auth-token-file\" ]; then shift; printf 'TOKEN=%s\\n' \"$(cat \"$1\")\"; fi; shift; done\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            token_file = Path(tmp) / "token"
            token_file.write_text("file-token\n", encoding="utf-8")
            help_env = Path(tmp) / "help-env.txt"
            base_env = os.environ | {
                "HOME": tmp,
                "SEMANTIC_MEMORY_MCP_BIN": str(fake),
                "SEMANTIC_MEMORY_HTTP_PORT": "1739",
                "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": str(token_file),
                "SM_BENCH_HTTP_AUTH_TOKEN": "secondary-secret",
                "CAPTURE_HELP_ENV": str(help_env),
            }

            empty_env = base_env | {"SEMANTIC_MEMORY_HTTP_TOKEN": ""}
            empty = subprocess.run(
                ["bash", str(RUN_SERVER)], text=True, capture_output=True, env=empty_env, check=False
            )
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertIn("ENV=unset|unset", empty.stdout)
            self.assertIn(str(token_file), empty.stdout)
            self.assertIn("TOKEN=file-token", empty.stdout)

            trimmed_env = base_env | {"SEMANTIC_MEMORY_HTTP_TOKEN": "  edge-token \n"}
            trimmed = subprocess.run(
                ["bash", str(RUN_SERVER)], text=True, capture_output=True, env=trimmed_env, check=False
            )
            self.assertEqual(trimmed.returncode, 0, trimmed.stderr)
            self.assertIn("ENV=unset|unset", trimmed.stdout)
            self.assertIn("/proc/self/fd/3", trimmed.stdout)
            self.assertIn("TOKEN=edge-token", trimmed.stdout)
            self.assertEqual(help_env.read_text(encoding="utf-8"), "unset|unset")

            unicode_env = base_env | {"SEMANTIC_MEMORY_HTTP_TOKEN": "ab\u00a0cd"}
            unicode_space = subprocess.run(
                ["bash", str(RUN_SERVER)], text=True, capture_output=True, env=unicode_env, check=False
            )
            self.assertEqual(unicode_space.returncode, 2)
            self.assertNotIn("ENV=", unicode_space.stdout)

    def test_http_launcher_failure_does_not_echo_token(self) -> None:
        secret = "launcher-secret-value"
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "semantic-memory-mcp"
            fake.write_text("#!/usr/bin/env bash\nif [ \"$1\" = \"--help\" ]; then echo '--http-port --http-auth-token-file'; else printf '%s\\n' \"$@\" >&2; exit 23; fi\n", encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ | {"HOME": tmp, "SEMANTIC_MEMORY_MCP_BIN": str(fake), "SEMANTIC_MEMORY_HTTP_PORT": "1739", "SEMANTIC_MEMORY_HTTP_TOKEN": secret}
            proc = subprocess.run(["bash", str(RUN_SERVER)], text=True, capture_output=True, env=env, check=False)
        self.assertEqual(proc.returncode, 23)
        self.assertIn("--http-auth-token-file", proc.stderr)
        self.assertIn("/proc/self/fd/3", proc.stderr)
        self.assertNotIn(secret, proc.stdout + proc.stderr)

    def test_benchmark_redacts_token_from_output(self) -> None:
        secret = "benchmark-secret-value"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake = tmp_path / "sm-bench"
            fake.write_text("#!/usr/bin/env bash\nif [ \"$1\" = \"--help\" ]; then printf '%s|%s' \"${SEMANTIC_MEMORY_HTTP_TOKEN-unset}\" \"${SM_BENCH_HTTP_AUTH_TOKEN-unset}\" > \"$CAPTURE_HELP_ENV\"; echo '--http-auth-token-file'; else printf '%s|%s' \"${SEMANTIC_MEMORY_HTTP_TOKEN-unset}\" \"${SM_BENCH_HTTP_AUTH_TOKEN-unset}\" > \"$CAPTURE_ENV_PATH\"; printf '%s\\n' \"$@\"; while [ \"$#\" -gt 0 ]; do if [ \"$1\" = \"--http-auth-token-file\" ]; then shift; cat \"$1\"; fi; shift; done; fi\n", encoding="utf-8")
            fake.chmod(0o755)
            fixtures = tmp_path / "fixtures.jsonl"
            fixtures.write_text('{"query":"memory"}\n', encoding="utf-8")
            capture_env = tmp_path / "child-env.txt"
            capture_help_env = tmp_path / "help-env.txt"
            env = os.environ | {
                "HOME": tmp,
                "SM_BENCH_BIN": str(fake),
                "SEMANTIC_MEMORY_HTTP_TOKEN": secret,
                "SM_BENCH_HTTP_AUTH_TOKEN": "secondary-secret",
                "CAPTURE_ENV_PATH": str(capture_env),
                "CAPTURE_HELP_ENV": str(capture_help_env),
            }
            proc = subprocess.run(
                [sys.executable, str(BENCHMARK), "--fixtures-file", str(fixtures), "--output-dir", str(tmp_path / "out")],
                text=True, capture_output=True, env=env, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("--http-auth-token-file", proc.stdout)
            self.assertIn("<redacted>", proc.stdout)
            self.assertNotIn(secret, proc.stdout + proc.stderr)
            self.assertEqual(capture_env.read_text(encoding="utf-8"), "unset|unset")
            self.assertEqual(capture_help_env.read_text(encoding="utf-8"), "unset|unset")
            match = re.search(r"--http-auth-token-file\s+(\S+)", proc.stdout)
            self.assertIsNotNone(match)
            assert match is not None
            self.assertFalse(Path(match.group(1)).exists())


if __name__ == "__main__":
    unittest.main()
