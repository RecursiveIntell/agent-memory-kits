#!/usr/bin/env python3
"""Canonical plugin tool receipt helpers.

The JSON shape intentionally mirrors the stable concepts from
llm-tool-runtime::ToolReceipt plus stack-ids::TraceCtx without requiring the
Rust crates at hook runtime. Keep this module dependency-light: Hermes/Codex
hooks call it after every material tool action.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from trace_ids import TraceCtx

SCHEMA = "llm-tool-runtime-compatible-tool-receipt-v1"


def compact_json(value: Any, limit: int = 300) -> str:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "..."


def status_record(tool_output: object) -> dict:
    """Extract high-signal status without storing raw tool output."""
    status: dict = {}
    if isinstance(tool_output, dict):
        for key in ("exit_code", "returncode", "status", "success", "ok", "timed_out"):
            if key in tool_output and isinstance(tool_output.get(key), (str, int, bool)):
                status[key] = tool_output.get(key)
        rc = tool_output.get("exit_code", tool_output.get("returncode"))
        if isinstance(rc, int):
            status.setdefault("success", rc == 0)
        if "error" in tool_output and tool_output.get("error"):
            status["error_digest"] = hashlib.sha256(
                str(tool_output.get("error")).encode("utf-8", "replace")
            ).hexdigest()
    return status


def canonical_tool_digest(tool: str, tool_input: dict, tool_output: object) -> str:
    digest_src = compact_json({"tool": tool, "input": tool_input, "output": tool_output}, 4000)
    return hashlib.sha256(digest_src.encode("utf-8", "replace")).hexdigest()


def build_tool_receipt(
    *,
    tool: str,
    summary: str,
    tool_input: dict,
    tool_output: object,
    cwd: str | None = None,
    session_id: str | None = None,
    scope: str = "tool",
    parent_trace_id: str | None = None,
) -> dict:
    digest = canonical_tool_digest(tool, tool_input, tool_output)
    trace_ctx = TraceCtx.create(scope=scope, parent_trace_id=parent_trace_id).to_dict()
    return {
        "schema": SCHEMA,
        "type": "tool_action_receipt",
        "trace_ctx": trace_ctx,
        "tool": tool,
        "summary": summary,
        "digest": {
            "algorithm": "sha256",
            "value": digest,
            "canonicalization": "json-sort-keys-compact-truncated-4000",
        },
        "status": status_record(tool_output),
        "cwd": cwd,
        "session_id": (session_id or "")[:12],
    }


def tool_receipt_content(receipt: dict, limit: int = 1200) -> str:
    trace_id = receipt.get("trace_ctx", {}).get("trace_id", "")
    digest = receipt.get("digest", {}).get("value", "")
    summary = str(receipt.get("summary") or receipt.get("tool") or "tool")
    content = (
        f"Tool receipt [{receipt.get('schema', SCHEMA)}]: {summary} "
        f"[trace_id:{trace_id}] [sha256:{digest}]"
    )
    if receipt.get("cwd"):
        content += f" (cwd: {receipt['cwd']})"
    if receipt.get("session_id"):
        content += f" (session: {receipt['session_id']})"
    content += " " + compact_json(receipt, limit)
    return content
