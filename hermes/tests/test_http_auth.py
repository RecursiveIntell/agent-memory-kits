#!/usr/bin/env python3
"""Focused coverage for Hermes semantic-memory HTTP authentication contract.

Tests the http_auth module's token resolution, normalization, and header
generation — the shared auth contract used by all HTTP clients.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))
import http_auth


class HttpAuthTokenResolution(unittest.TestCase):
    """Test token file default, env override, and normalization."""

    def test_default_token_file_path(self):
        """default_http_token_file returns the canonical path under home."""
        path = http_auth.default_http_token_file()
        self.assertTrue(str(path).endswith(".hermes/semantic-memory-http-1739.token"))

    def test_normalize_rejects_empty_token(self):
        """Empty strings are rejected."""
        self.assertIsNone(http_auth.normalize_http_token(""))
        self.assertIsNone(http_auth.normalize_http_token("   "))

    def test_normalize_rejects_internal_whitespace(self):
        """Tokens with internal whitespace are rejected (injection risk)."""
        self.assertIsNone(http_auth.normalize_http_token("token with spaces"))
        self.assertIsNone(http_auth.normalize_http_token("token\twith\ttabs"))
        self.assertIsNone(http_auth.normalize_http_token("token\nwith\nnewlines"))

    def test_normalize_accepts_valid_token(self):
        """Valid alphanumeric tokens pass through."""
        self.assertEqual(http_auth.normalize_http_token("abc123"), "abc123")
        self.assertEqual(http_auth.normalize_http_token("  abc123  "), "abc123")

    def test_resolve_explicit_env_token(self):
        """SEMANTIC_MEMORY_HTTP_TOKEN env var takes priority."""
        with mock.patch.dict(os.environ, {"SEMANTIC_MEMORY_HTTP_TOKEN": "env-tok-123"}, clear=False):
            self.assertEqual(http_auth.resolve_http_token(), "env-tok-123")

    def test_resolve_explicit_env_token_rejects_whitespace(self):
        """Whitespace-containing env tokens are rejected."""
        with mock.patch.dict(os.environ, {"SEMANTIC_MEMORY_HTTP_TOKEN": "bad token"}, clear=False):
            self.assertIsNone(http_auth.resolve_http_token())

    def test_resolve_token_from_file(self):
        """Token is read from the configured token file."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".token", delete=False) as f:
            f.write("file-tok-456\n")
            f.flush()
            token_path = f.name
        try:
            with mock.patch.dict(os.environ, {
                "SEMANTIC_MEMORY_HTTP_TOKEN": "",
                "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": token_path,
            }, clear=False):
                self.assertEqual(http_auth.resolve_http_token(), "file-tok-456")
        finally:
            os.unlink(token_path)

    def test_resolve_returns_none_when_no_source(self):
        """Returns None when no env var and no token file exists."""
        with mock.patch.dict(os.environ, {
            "SEMANTIC_MEMORY_HTTP_TOKEN": "",
            "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": "/nonexistent/path/token",
        }, clear=False):
            self.assertIsNone(http_auth.resolve_http_token())

    def test_authorization_headers_with_token(self):
        """Bearer header is generated when token resolves."""
        with mock.patch.dict(os.environ, {"SEMANTIC_MEMORY_HTTP_TOKEN": "test-bearer"}, clear=False):
            headers = http_auth.authorization_headers()
            self.assertEqual(headers, {"Authorization": "Bearer test-bearer"})

    def test_authorization_headers_without_token(self):
        """Empty dict when no token resolves."""
        with mock.patch.dict(os.environ, {
            "SEMANTIC_MEMORY_HTTP_TOKEN": "",
            "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": "/nonexistent/token",
        }, clear=False):
            headers = http_auth.authorization_headers()
            self.assertEqual(headers, {})


if __name__ == "__main__":
    unittest.main()