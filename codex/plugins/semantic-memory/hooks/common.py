#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def debug(label: str) -> None:
    target = os.environ.get("SEMANTIC_MEMORY_HOOK_DEBUG")
    if not target:
        return
    try:
        with open(Path(target).expanduser(), "a", encoding="utf-8") as fh:
            fh.write(label + "\n")
    except Exception:
        pass


def resolve_binary() -> str | None:
    env = os.environ.get("SEMANTIC_MEMORY_MCP_BIN")
    if env and os.access(os.path.expanduser(env), os.X_OK):
        return os.path.expanduser(env)
    for candidate in (
        Path.home() / "Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp",
        Path.home() / ".local/bin/semantic-memory-mcp",
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    which = shutil.which("semantic-memory-mcp")
    if which:
        return which
    cargo = Path.home() / ".cargo/bin/semantic-memory-mcp"
    if cargo.exists() and os.access(cargo, os.X_OK):
        return str(cargo)
    return None


def binary_help(binary: str) -> str:
    try:
        proc = subprocess.run(
            [binary, "--help"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return ""
    return f"{proc.stdout}\n{proc.stderr}"


def binary_supports(binary: str, flag: str) -> bool:
    return flag in binary_help(binary)


def memory_dir() -> str:
    return os.environ.get("SEMANTIC_MEMORY_DIR", str(Path.home() / ".local/share/semantic-memory"))


def http_base() -> str:
    explicit = os.environ.get("SEMANTIC_MEMORY_HTTP_URL")
    if explicit:
        return explicit.rstrip("/")
    port = os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", "1739")
    return f"http://127.0.0.1:{port}"


def http_post(path: str, payload: dict, timeout: float = 4.0) -> dict | None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        http_base() + path,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (OSError, urllib.error.URLError, TimeoutError):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def rpc_call(tool: str, arguments: dict, timeout: int = 8) -> dict | None:
    binary = resolve_binary()
    if not binary:
        return None
    memdir = memory_dir()
    Path(memdir).mkdir(parents=True, exist_ok=True)
    reqs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "codex-semantic-memory-hook", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
    ]
    stdin = "\n".join(json.dumps(item) for item in reqs) + "\n"
    embedder = os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle")
    tool_profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    base_args = ["--memory-dir", memdir]
    if tool_profile and binary_supports(binary, "--tool-profile"):
        base_args.extend(["--tool-profile", tool_profile])
    commands = [[binary, *base_args]]
    if embedder:
        commands.insert(0, [binary, *base_args, "--embedder", embedder])
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                input=stdin,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except Exception:
            continue
        for line in proc.stdout.splitlines():
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("id") != 2:
                continue
            try:
                return json.loads(msg["result"]["content"][0]["text"])
            except Exception:
                return None
    return None


def superseded_fact_ids(timeout: int = 5) -> set[str]:
    result = rpc_call("sm_list_graph_edges", {}, timeout=timeout) or {}
    targets: set[str] = set()
    for edge in result.get("edges") or []:
        if "supersedes" not in json.dumps(edge, sort_keys=True):
            continue
        target = edge.get("target")
        if isinstance(target, str):
            targets.add(target)
    return targets


def drop_superseded_hits(hits: list[dict], timeout: int = 5) -> list[dict]:
    targets = superseded_fact_ids(timeout=timeout)
    if not targets:
        return hits
    fresh = [hit for hit in hits if hit.get("result_id") not in targets]
    return fresh or hits


def read_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def emit_context(event_name: str, text: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": text,
                }
            },
            separators=(",", ":"),
        )
    )
