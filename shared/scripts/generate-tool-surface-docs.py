#!/usr/bin/env python3
"""generate-tool-surface-docs.py — mechanically generate MCP tool surface docs.

Reads plugin manifests and produces a JSON artifact with per-profile tool counts
and tool names. Used by doctor to catch README/docs drift.

Usage:
  python generate-tool-surface-docs.py --out tool-surface.json [--format json|markdown]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_mcp_tool_list(command: str, args: list[str], timeout: int = 15) -> list[dict] | None:
    """Try to get tools/list from an MCP server via stdio. Returns None on failure."""
    try:
        proc = subprocess.run(
            [command] + args,
            input=json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 1}),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        for line in proc.stdout.strip().split("\n"):
            try:
                msg = json.loads(line)
                if "result" in msg and "tools" in msg.get("result", {}):
                    return msg["result"]["tools"]
            except json.JSONDecodeError:
                continue
    except Exception:
        return None
    return None


def get_profile_tools(profile: str, binary_path: str | None = None) -> dict:
    """Get tool count and names for a semantic-memory-mcp profile."""
    binary = binary_path or (
        os.path.expanduser("~/.cargo/bin/semantic-memory-mcp")
    )
    if not os.path.isfile(binary):
        return {
            "tool_count": None,
            "tools": [],
            "available": False,
            "error": f"binary not found at {binary}",
        }
    tools = get_mcp_tool_list(binary, ["--tool-profile", profile, "--memory-dir", "/tmp/sm-gen-docs"])
    if tools is None:
        return {
            "tool_count": None,
            "tools": [],
            "available": False,
            "error": "failed to get tools/list",
        }
    return {
        "tool_count": len(tools),
        "tools": [{"name": t.get("name", ""), "description": t.get("description", "")} for t in tools],
        "available": True,
    }


def get_claim_ledger_tools() -> dict:
    """Get claim-ledger companion tool list."""
    script = os.path.join(
        os.path.dirname(__file__), "claim-ledger-mcp.py"
    )
    if not os.path.isfile(script):
        return {"tool_count": None, "tools": [], "available": False, "error": "script not found"}
    tools = get_mcp_tool_list(sys.executable, [script])
    if tools is None:
        return {"tool_count": None, "tools": [], "available": False, "error": "failed to get tools/list"}
    return {
        "tool_count": len(tools),
        "tools": [{"name": t.get("name", ""), "description": t.get("description", "")} for t in tools],
        "available": True,
    }


def get_context_governor_tools() -> dict:
    """Get context-governor tool surface (CLI commands, not MCP)."""
    binary = shutil.which("context-governor") or os.path.expanduser("~/.cargo/bin/context-governor")
    if not os.path.isfile(binary):
        return {"tool_count": None, "tools": [], "available": False, "error": "binary not found"}
    commands = [
        "compact", "store", "expand", "search", "status", "prune", "diff", "boundary-audit",
        "audit-tool-surface", "audit-compression-boundary", "eval-governed-memory",
        "eval-rag-leakage", "screen-conflicts", "select-route",
    ]
    return {
        "tool_count": len(commands),
        "tools": [{"name": c, "description": f"context-governor CLI command: {c}"} for c in commands],
        "available": True,
    }


def generate_artifact(out_path: str, sm_binary: str | None = None) -> dict:
    """Generate the tool-surface artifact."""
    artifact = {
        "schema": "ToolSurfaceDocV1",
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "profiles": {},
        "companions": {},
    }

    for profile in ["lean", "standard", "full", "admin"]:
        artifact["profiles"][profile] = get_profile_tools(profile, sm_binary)

    artifact["companions"]["claim-ledger"] = get_claim_ledger_tools()
    artifact["companions"]["context-governor"] = get_context_governor_tools()

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)

    return artifact


def to_markdown(artifact: dict) -> str:
    """Convert artifact to markdown table."""
    lines = ["# Tool Surface Report", ""]
    lines.append("Generated: " + artifact.get("generated_at", "unknown"))
    lines.append("")
    lines.append("## Profiles")
    lines.append("| Profile | Available | Tool Count |")
    lines.append("|---------|-----------|------------|")
    for name, data in artifact.get("profiles", {}).items():
        avail = "yes" if data.get("available") else "no"
        count = data.get("tool_count") or "N/A"
        lines.append(f"| {name} | {avail} | {count} |")
    lines.append("")
    lines.append("## Companions")
    lines.append("| Companion | Available | Tool Count |")
    lines.append("|-----------|-----------|------------|")
    for name, data in artifact.get("companions", {}).items():
        avail = "yes" if data.get("available") else "no"
        count = data.get("tool_count") or "N/A"
        lines.append(f"| {name} | {avail} | {count} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MCP tool-surface docs")
    parser.add_argument("--out", required=True, help="Output file path")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--sm-binary", default=None, help="Path to semantic-memory-mcp binary")
    args = parser.parse_args()

    artifact = generate_artifact(args.out, args.sm_binary)

    if args.format == "markdown":
        md = to_markdown(artifact)
        md_path = args.out.rsplit(".", 1)[0] + ".md"
        with open(md_path, "w") as f:
            f.write(md)
        print(f"Markdown written to {md_path}")
    else:
        print(f"JSON written to {args.out}")

    # Summary
    for name, data in artifact.get("profiles", {}).items():
        if data.get("available"):
            print(f"  {name}: {data['tool_count']} tools")
        else:
            print(f"  {name}: unavailable ({data.get('error', 'unknown')})")
    for name, data in artifact.get("companions", {}).items():
        if data.get("available"):
            print(f"  {name}: {data['tool_count']} tools")
        else:
            print(f"  {name}: unavailable ({data.get('error', 'unknown')})")


if __name__ == "__main__":
    main()