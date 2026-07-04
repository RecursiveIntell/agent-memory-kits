#!/usr/bin/env python3
"""agent-guard-mcp.py — MCP server for agent security posture reporting.

Exposes admin-only tools for checking Linux security mechanism availability:
  agent_guard_security_posture — report available cgroup/seccomp/Landlock/BPF
  agent_guard_check_process      — check if a process is sandboxed

This is a skeleton MCP server. It reports what mechanisms are available on the
host but does not implement sandboxing itself. agent-guard (the Rust crate)
provides the actual control plane.

Usage:
  python agent-guard-mcp.py --list-tools   # List tools
  python agent-guard-mcp.py                 # Run as MCP stdio server
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

TOOLS = [
    {
        "name": "agent_guard_security_posture",
        "description": (
            "ADMIN ONLY: Report which Linux security mechanisms are available "
            "on this host (cgroup v2, seccomp, Landlock, BPF LSM, eBPF). "
            "Returns a SecurityPostureV1 JSON. This is agent security infrastructure."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "agent_guard_check_process",
        "description": (
            "ADMIN ONLY: Check if a process (by PID) is currently sandboxed "
            "using any available Linux security mechanism. Returns a "
            "ProcessCheckV1 JSON. This is agent security infrastructure."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "Process ID to check"}
            },
            "required": ["pid"],
        },
    },
]


def check_cgroup_v2() -> bool:
    """Check if cgroup v2 is available."""
    return os.path.exists("/sys/fs/cgroup/cgroup.controllers")


def check_seccomp() -> bool:
    """Check if seccomp is available."""
    return os.path.exists("/proc/self/status") and "Seccomp" in open("/proc/self/status").read()


def check_landlock() -> bool:
    """Check if Landlock is available (kernel config dependent)."""
    try:
        result = subprocess.run(
            ["cat", "/sys/kernel/security/lsm"],
            capture_output=True, text=True, timeout=2
        )
        return "landlock" in (result.stdout or "").lower()
    except Exception:
        return False


def check_bpf_lsm() -> bool:
    """Check if BPF LSM is available."""
    try:
        result = subprocess.run(
            ["cat", "/sys/kernel/security/lsm"],
            capture_output=True, text=True, timeout=2
        )
        return "bpf" in (result.stdout or "").lower()
    except Exception:
        return False


def handle_tool_call(name: str, arguments: dict) -> dict:
    if name == "agent_guard_security_posture":
        return {
            "schema": "SecurityPostureV1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "available_mechanisms": {
                "cgroup_v2": check_cgroup_v2(),
                "seccomp": check_seccomp(),
                "landlock": check_landlock(),
                "bpf_lsm": check_bpf_lsm(),
            },
            "platform": sys.platform,
            "claim_boundary": "Reports mechanism availability only, not configuration or enforcement.",
        }
    elif name == "agent_guard_check_process":
        pid = arguments.get("pid", 0)
        # Basic check — in production this would use agent-guard Rust crate
        try:
            result = subprocess.run(
                ["cat", f"/proc/{pid}/cgroup"],
                capture_output=True, text=True, timeout=2
            )
            cgroup_info = result.stdout if result.returncode == 0 else "unknown"
        except Exception:
            cgroup_info = "error"

        try:
            result = subprocess.run(
                ["cat", f"/proc/{pid}/status"],
                capture_output=True, text=True, timeout=2
            )
            seccomp_line = [l for l in (result.stdout or "").split("\n") if "Seccomp" in l]
            seccomp_status = seccomp_line[0] if seccomp_line else "unknown"
        except Exception:
            seccomp_status = "error"

        return {
            "schema": "ProcessCheckV1",
            "pid": pid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cgroup": cgroup_info[:500],
            "seccomp": seccomp_status,
            "claim_boundary": "Basic /proc check only, not full sandbox verification.",
        }
    else:
        return {"error": f"unknown tool: {name}"}


def run_mcp_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id", 0)

        if method == "initialize":
            response = {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "agent-guard", "version": "0.1.0"},
                },
            }
        elif method == "tools/list":
            response = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            params = msg.get("params", {})
            result = handle_tool_call(params.get("name", ""), params.get("arguments", {}))
            response = {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }
        else:
            response = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"unknown method: {method}"}}

        print(json.dumps(response))
        sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent guard MCP server")
    parser.add_argument("--list-tools", action="store_true")
    args = parser.parse_args()
    if args.list_tools:
        print(json.dumps(TOOLS, indent=2))
        return
    run_mcp_stdio()


if __name__ == "__main__":
    main()