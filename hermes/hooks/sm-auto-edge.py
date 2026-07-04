#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from common import debug, http_post, read_payload

SKIP_TOOLS = {"browser_snapshot", "browser_console", "browser_vision", "browser_get_images", "browser_scroll", "todo"}


def compact_json(value, limit: int = 300) -> str:
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "..."


def summarize(tool_name: str, tool_input: dict, tool_output: object) -> str:
    if tool_name == "terminal":
        return f"terminal: {str(tool_input.get('command') or '')[:160]}"
    if tool_name in {"read_file", "write_file", "patch"}:
        return f"{tool_name}: {tool_input.get('path') or tool_input.get('file_path') or ''}"
    if tool_name == "search_files":
        return f"search_files: {tool_input.get('pattern') or ''} in {tool_input.get('path') or '.'}"
    if tool_name == "delegate_task":
        return f"delegate_task: {str(tool_input.get('goal') or '')[:160]}"
    if tool_name == "execute_code":
        return f"execute_code: {len(str(tool_input.get('code') or ''))} chars"
    return f"{tool_name}: {compact_json(tool_input, 160)}"


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
            status["error_digest"] = hashlib.sha256(str(tool_output.get("error")).encode("utf-8", "replace")).hexdigest()
    return status


def main() -> int:
    debug("post_tool_use semantic-memory receipt")
    payload = read_payload()
    tool_name = str(payload.get("tool_name") or payload.get("name") or "unknown")
    if tool_name.startswith("sm_") or tool_name in SKIP_TOOLS:
        return 0
    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("args") or {}
    if not isinstance(tool_input, dict):
        tool_input = {"value": tool_input}
    tool_output = payload.get("tool_output") or payload.get("output") or payload.get("result")
    summary = summarize(tool_name, tool_input, tool_output)
    digest_src = compact_json({"tool": tool_name, "input": tool_input, "output": tool_output}, 4000)
    digest = hashlib.sha256(digest_src.encode("utf-8", "replace")).hexdigest()
    trace_id = f"tool:{tool_name}:{digest[:16]}"
    cwd = payload.get("cwd") or payload.get("workspaceRoot")
    session_id = str(payload.get("session_id") or payload.get("session") or "")
    receipt = {
        "schema": "semantic-memory-tool-receipt-v1",
        "type": "tool_action_receipt",
        "trace_id": trace_id,
        "tool": tool_name,
        "summary": summary,
        "digest": {"algorithm": "sha256", "value": digest, "canonicalization": "json-sort-keys-compact-truncated-4000"},
        "status": status_record(tool_output),
        "cwd": cwd,
        "session_id": session_id[:12] if session_id else "",
    }
    content = f"Tool receipt [{receipt['schema']}]: {summary} [trace_id:{trace_id}] [sha256:{digest}]"
    if cwd:
        content += f" (cwd: {cwd})"
    if session_id:
        content += f" (session: {session_id[:12]})"
    content += " " + compact_json(receipt, 1200)
    # Warm HTTP only: fail open instead of cold-spawning writes from every tool call.
    http_post("/add", {"content": content, "namespace": "tool-receipts", "source": "hermes-post-tool-use-hook"}, timeout=3.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
