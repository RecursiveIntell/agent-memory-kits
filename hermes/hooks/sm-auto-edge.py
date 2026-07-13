#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

HOOK_DIR = Path(__file__).resolve().parent


def _shared_scripts_dir() -> Path:
    roots = []
    configured = __import__("os").environ.get("SEMANTIC_MEMORY_KIT_ROOT")
    if configured:
        roots.append(Path(configured).expanduser())
    roots.extend([HOOK_DIR.parents[1], Path.home() / "Coding/agent-memory-kits"])
    for root in roots:
        candidate = root / "shared" / "scripts"
        if (candidate / "tool_receipts.py").is_file():
            return candidate
    raise RuntimeError("shared tool receipt support is unavailable")


SHARED_SCRIPTS = _shared_scripts_dir()
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from common import debug, http_post, read_payload
from tool_receipts import build_tool_receipt

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


def main() -> int:
    debug("post_tool_call semantic-memory receipt")
    payload = read_payload()
    tool_name = str(payload.get("tool_name") or payload.get("name") or "unknown")
    if tool_name.startswith("sm_") or tool_name in SKIP_TOOLS:
        return 0
    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("args") or {}
    if not isinstance(tool_input, dict):
        tool_input = {"value": tool_input}
    tool_output = payload.get("tool_output") or payload.get("output") or payload.get("result")
    summary = summarize(tool_name, tool_input, tool_output)
    cwd = payload.get("cwd") or payload.get("workspaceRoot")
    session_id = str(payload.get("session_id") or payload.get("session") or "")
    receipt = build_tool_receipt(
        tool=tool_name,
        summary=summary,
        tool_input=tool_input,
        tool_output=tool_output,
        cwd=cwd,
        session_id=session_id,
        scope="tool",
        parent_trace_id=payload.get("parent_trace_id") or payload.get("trace_id"),
        task_id=payload.get("task_id"),
        tool_call_id=payload.get("tool_call_id") or payload.get("call_id"),
        api_request_id=payload.get("api_request_id") or payload.get("request_id"),
    )
    # Warm HTTP only: fail open instead of cold-spawning writes from every tool call.
    http_post("/add-tool-receipt", {"receipt": receipt, "namespace": "tool-receipts", "source": "hermes-post-tool-call-hook"}, timeout=3.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
