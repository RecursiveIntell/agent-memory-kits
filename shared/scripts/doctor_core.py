#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

MEMORY_DIR = Path(os.environ.get("SEMANTIC_MEMORY_DIR", Path.home() / ".local/share/semantic-memory")).expanduser()
HTTP_URL = os.environ.get("SEMANTIC_MEMORY_HTTP_URL") or f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"


def ok(label: str, detail: str = "") -> None:
    print(f"OK   {label}{': ' + detail if detail else ''}")


def warn(label: str, detail: str = "") -> None:
    print(f"WARN {label}{': ' + detail if detail else ''}")


def fail(label: str, detail: str = "") -> None:
    print(f"FAIL {label}{': ' + detail if detail else ''}")


def resolve_binary() -> Path | None:
    candidates: list[Path] = []
    env = os.environ.get("SEMANTIC_MEMORY_MCP_BIN")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.extend([
        Path.home() / "Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp",
        Path.home() / ".local/bin/semantic-memory-mcp",
    ])
    which = shutil.which("semantic-memory-mcp")
    if which:
        candidates.append(Path(which))
    candidates.append(Path.home() / ".cargo/bin/semantic-memory-mcp")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def binary_help(binary: Path) -> str:
    try:
        proc = subprocess.run([str(binary), "--help"], text=True, capture_output=True, timeout=5, check=False)
    except Exception as exc:
        fail("binary --help", str(exc))
        return ""
    if proc.returncode == 0:
        ok("binary --help", str(binary))
    else:
        warn("binary --help", proc.stderr.strip()[-300:])
    return f"{proc.stdout}\n{proc.stderr}"


def http_health() -> None:
    try:
        with urllib.request.urlopen(HTTP_URL.rstrip("/") + "/health", timeout=2) as resp:
            body = resp.read().decode("utf-8", "replace")[:300]
        ok("warm HTTP health", f"{HTTP_URL} {body}")
    except Exception as exc:
        warn("warm HTTP health", f"{HTTP_URL} unavailable ({exc}); MCP stdio can still work")


def rpc_tools_list(binary: Path) -> bool:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "semantic-memory-agent-kit-doctor", "version": "1"},
        },
    }
    reqs = [init, {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}]
    stdin = "\n".join(json.dumps(x) for x in reqs) + "\n"
    cmd = [str(binary), "--memory-dir", str(MEMORY_DIR), "--embedder", os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle")]
    help_text = binary_help(binary)
    profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    if "--tool-profile" in help_text and profile:
        cmd.extend(["--tool-profile", profile])
    try:
        proc = subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=25, check=False)
    except Exception as exc:
        fail("MCP tools/list", str(exc))
        return False
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") == 2:
            tools = msg.get("result", {}).get("tools", [])
            names = {t.get("name") for t in tools}
            required = {"sm_search", "sm_add_fact", "sm_stats", "sm_supersede_fact"}
            missing = sorted(required - names)
            if missing:
                fail("MCP tools/list", "missing " + ", ".join(missing))
                return False
            ok("MCP tools/list", f"{len(tools)} tools exposed; required semantic-memory tools present")
            return True
    detail = (proc.stderr or proc.stdout)[-500:]
    fail("MCP tools/list", detail.strip())
    return False


def main() -> int:
    print(f"Semantic Memory Agent Kit Doctor\nmemory_dir: {MEMORY_DIR}\nhttp_url:   {HTTP_URL}\n")
    binary = resolve_binary()
    if not binary:
        fail("semantic-memory-mcp binary", "not found; run shared/scripts/install_semantic_memory_mcp.sh or cargo install semantic-memory-mcp")
        return 1
    ok("semantic-memory-mcp binary", str(binary))
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    ok("memory dir", str(MEMORY_DIR))
    http_health()
    return 0 if rpc_tools_list(binary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
