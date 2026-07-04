#!/usr/bin/env python3
"""trace_ids.py — stack-ids-compatible trace ID and content digest helpers.

Provides:
  - generate_trace_id(scope) -> "trace:{scope}:{uuid_hex}"
  - generate_content_digest(content) -> "sha256:{hexdigest}"
  - TraceCtx dataclass (scope, trace_id, timestamp, parent_trace_id)

All generated receipts in the plugin stack should include a TraceCtx so that
receipts from different hosts (Hermes, Codex, Claude) can be correlated.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def generate_trace_id(scope: str = "plugin") -> str:
    """Generate a unique trace ID with scope prefix."""
    return f"trace:{scope}:{uuid.uuid4().hex[:16]}"


def generate_content_digest(content: str) -> str:
    """Generate a SHA-256 digest of content with prefix."""
    return f"sha256:{hashlib.sha256(content.encode('utf-8', 'replace')).hexdigest()}"


@dataclass
class TraceCtx:
    """Trace context for receipt correlation across hosts."""

    scope: str
    trace_id: str
    timestamp: str = ""
    parent_trace_id: str | None = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("parent_trace_id") is None:
            del d["parent_trace_id"]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TraceCtx":
        return cls(
            scope=d.get("scope", "unknown"),
            trace_id=d.get("trace_id", ""),
            timestamp=d.get("timestamp", ""),
            parent_trace_id=d.get("parent_trace_id"),
        )

    @classmethod
    def create(cls, scope: str = "plugin", parent_trace_id: str | None = None) -> "TraceCtx":
        return cls(
            scope=scope,
            trace_id=generate_trace_id(scope),
            parent_trace_id=parent_trace_id,
        )