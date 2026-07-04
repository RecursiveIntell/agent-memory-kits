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
        Path.home() / ".cargo/bin/semantic-memory-mcp",
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("semantic-memory-mcp")


def memory_dir() -> str:
    return os.environ.get("SEMANTIC_MEMORY_DIR", str(Path.home() / ".local/share/semantic-memory"))


def http_base() -> str:
    explicit = os.environ.get("SEMANTIC_MEMORY_HTTP_URL")
    if explicit:
        return explicit.rstrip("/")
    port = os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", "1739")
    return f"http://127.0.0.1:{port}"


def http_get(path: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(http_base() + path, timeout=timeout) as response:
            raw = response.read()
    except (OSError, urllib.error.URLError, TimeoutError):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


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


def binary_help(binary: str) -> str:
    try:
        proc = subprocess.run([binary, "--help"], text=True, capture_output=True, timeout=3, check=False)
    except Exception:
        return ""
    return f"{proc.stdout}\n{proc.stderr}"


def rpc_call(tool: str, arguments: dict, timeout: int = 8) -> dict | None:
    binary = resolve_binary()
    if not binary:
        return None
    memdir = memory_dir()
    Path(memdir).mkdir(parents=True, exist_ok=True)
    reqs = [
        {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes-semantic-memory-hook","version":"1"}}},
        {"jsonrpc":"2.0","method":"notifications/initialized"},
        {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":arguments}},
    ]
    stdin = "\n".join(json.dumps(item) for item in reqs) + "\n"
    cmd = [binary, "--memory-dir", memdir]
    embedder = os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle")
    if embedder:
        cmd.extend(["--embedder", embedder])
    profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    if profile and "--tool-profile" in binary_help(binary):
        cmd.extend(["--tool-profile", profile])
    try:
        proc = subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=timeout, check=False)
    except Exception:
        return None
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


def read_payload() -> dict:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def emit_context(event_name: str, text: str) -> None:
    print(json.dumps({"hookSpecificOutput":{"hookEventName":event_name,"additionalContext":text}}, separators=(",", ":")))


def hit_namespace(hit: dict) -> str:
    namespace = hit.get("namespace")
    if isinstance(namespace, str):
        return namespace
    source = str(hit.get("source") or "")
    if "namespace:" in source:
        return source.split("namespace:", 1)[1].split()[0].strip('"{}')
    return ""


def drop_excluded_namespaces(hits: list[dict]) -> list[dict]:
    raw = os.environ.get("SM_RECALL_EXCLUDE_NS", "mixed,research,recursiveintell,twitter")
    excluded = {item.strip() for item in raw.split(",") if item.strip()}
    if not excluded:
        return hits
    return [hit for hit in hits if hit_namespace(hit) not in excluded]


def drop_noisy_autorecall_hits(hits: list[dict]) -> list[dict]:
    noisy = ("grok conversation", "twitter activity", "external_research_notes", "https://x.com/")
    return [hit for hit in hits if not any(marker in str(hit.get("content") or "").lower() for marker in noisy)]
