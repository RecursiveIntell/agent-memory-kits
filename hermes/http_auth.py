"""Shared authentication contract for Hermes semantic-memory HTTP clients."""
from __future__ import annotations

import os
from pathlib import Path


DEFAULT_HTTP_TOKEN_FILE = ".hermes/semantic-memory-http-1739.token"


def default_http_token_file() -> Path:
    """Return the private, port-1739 token-file location.

    The file is intentionally not created automatically: an empty or missing
    file must not accidentally enable an unauthenticated warm HTTP server.
    """
    return Path(os.path.expanduser("~")) / DEFAULT_HTTP_TOKEN_FILE


def normalize_http_token(raw: str) -> str | None:
    """Normalize one token and reject empty or internally-whitespace values."""
    token = raw.strip()
    if not token or any(char.isspace() for char in token):
        return None
    return token


def resolve_http_token() -> str | None:
    """Resolve the HTTP token without logging its value.

    Precedence is an explicit value, an explicitly configured file, and then
    the canonical Hermes port-1739 token file.
    """
    explicit_raw = os.environ.get("SEMANTIC_MEMORY_HTTP_TOKEN")
    if explicit_raw:
        return normalize_http_token(explicit_raw)

    token_file = os.environ.get("SEMANTIC_MEMORY_HTTP_TOKEN_FILE")
    path = Path(os.path.expanduser(token_file)) if token_file else default_http_token_file()
    try:
        token = normalize_http_token(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return token


def authorization_headers() -> dict[str, str]:
    """Return the Bearer header when the configured token resolves."""
    token = resolve_http_token()
    return {"Authorization": f"Bearer {token}"} if token else {}
