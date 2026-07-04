#!/usr/bin/env python3
"""forge-admin-mcp.py — MCP server for Forge/CEA patch verification admin tools.

Exposes admin-only tools for patch verification, causal edit attribution,
risk prediction, and evidence export. These are NOT daily-lean tools — they
belong in the admin/full profile only.

Tools:
  forge_verify_patch    — verify a patch/change before apply
  forge_get_attribution — query CEA graph for attribution data
  forge_predict_risk    — predict edit risk for a given edit signature
  forge_export_evidence — export Forge evidence bundle

Usage:
  python forge-admin-mcp.py --list-tools          # List available tools
  python forge-admin-mcp.py                        # Run as MCP stdio server
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = [
    {
        "name": "forge_verify_patch",
        "description": (
            "ADMIN ONLY: Verify a patch/change before apply. Runs a check command "
            "in a sandboxed workspace, captures results, and emits a "
            "PatchVerificationReceiptV1 with disposition (promote/reject/quarantine). "
            "This is patch-verification/release-gate infrastructure, not daily recall."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Path to the repository to verify"},
                "claim": {"type": "string", "description": "Claim about the patch being verified"},
                "check_cmd": {"type": "string", "description": "Command to run for verification"},
            },
            "required": ["repo_path", "claim", "check_cmd"],
        },
    },
    {
        "name": "forge_get_attribution",
        "description": (
            "ADMIN ONLY: Query causal edit attribution (CEA) graph for attribution "
            "data. Returns AttributionTriple[] linking edits to check results. "
            "Requires forge-engine binary. This is patch-verification infrastructure."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "graph_path": {"type": "string", "description": "Path to CEA graph database"},
                "run_id": {"type": "string", "description": "Run ID to query attribution for"},
            },
            "required": ["graph_path"],
        },
    },
    {
        "name": "forge_predict_risk",
        "description": (
            "ADMIN ONLY: Predict future edit risk for a given edit operation signature. "
            "Uses the CEA causal graph to predict whether similar edits are likely to "
            "pass or fail. Requires forge-engine binary. This is release-gate infrastructure."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "graph_path": {"type": "string", "description": "Path to CEA graph database"},
                "edit_signature": {"type": "string", "description": "Edit operation signature to predict"},
            },
            "required": ["graph_path", "edit_signature"],
        },
    },
    {
        "name": "forge_export_evidence",
        "description": (
            "ADMIN ONLY: Export Forge evidence bundle for claim-ledger integration. "
            "Produces an exportable evidence bundle that can be stored in claim-ledger "
            "as proof of verification. This is release-gate infrastructure."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "receipt_path": {"type": "string", "description": "Path to PatchVerificationReceiptV1 JSON"},
                "claim_id": {"type": "string", "description": "Claim-ledger claim ID to attach evidence to"},
            },
            "required": ["receipt_path"],
        },
    },
]


def list_tools() -> list[dict]:
    """Return tool definitions."""
    return TOOLS


def handle_tool_call(name: str, arguments: dict) -> dict:
    """Handle a tool call and return result."""
    if name == "forge_verify_patch":
        return _handle_verify_patch(arguments)
    elif name == "forge_get_attribution":
        return _handle_get_attribution(arguments)
    elif name == "forge_predict_risk":
        return _handle_predict_risk(arguments)
    elif name == "forge_export_evidence":
        return _handle_export_evidence(arguments)
    else:
        return {"error": f"unknown tool: {name}"}


def _handle_verify_patch(args: dict) -> dict:
    """Run verify-patch.py with the given arguments."""
    script = Path(__file__).resolve().parent / "verify-patch.py"
    if not script.exists():
        return {"error": f"verify-patch.py not found at {script}"}
    cmd = [
        sys.executable, str(script),
        "--repo", args.get("repo_path", ""),
        "--claim", args.get("claim", ""),
        "--check-cmd", args.get("check_cmd", ""),
        "--out-dir", "/tmp/forge-admin-receipts",
        "--no-memory",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        if proc.returncode == 0:
            result = json.loads(proc.stdout)
            return {"ok": True, "result": result}
        else:
            return {"ok": False, "error": proc.stderr[-500:], "exit_code": proc.returncode}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_get_attribution(args: dict) -> dict:
    """Query CEA graph for attribution data."""
    binary = os.path.expanduser("~/.cargo/bin/forge-engine")
    if not os.path.isfile(binary):
        return {
            "available": False,
            "error": "forge-engine binary not installed",
            "claim_boundary": "CEA attribution requires the forge-engine Rust binary",
        }
    # Would call forge-engine with attribution query
    return {"available": True, "message": "forge-engine binary found but attribution query not yet wired"}


def _handle_predict_risk(args: dict) -> dict:
    """Predict edit risk using CEA graph."""
    binary = os.path.expanduser("~/.cargo/bin/forge-engine")
    if not os.path.isfile(binary):
        return {
            "available": False,
            "error": "forge-engine binary not installed",
            "claim_boundary": "Risk prediction requires the forge-engine Rust binary",
        }
    return {"available": True, "message": "forge-engine binary found but risk prediction not yet wired"}


def _handle_export_evidence(args: dict) -> dict:
    """Export Forge evidence bundle."""
    receipt_path = args.get("receipt_path", "")
    if not os.path.isfile(receipt_path):
        return {"error": f"receipt not found at {receipt_path}"}
    with open(receipt_path) as f:
        receipt = json.load(f)
    bundle = {
        "schema": "ForgeEvidenceBundleV1",
        "source_receipt": receipt.get("schema", "unknown"),
        "trace_id": receipt.get("trace_id", ""),
        "claim": receipt.get("claim", ""),
        "disposition": receipt.get("disposition", ""),
        "check_result": receipt.get("check_result", {}),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"ok": True, "bundle": bundle}


def run_mcp_stdio() -> None:
    """Run as a simple MCP stdio server."""
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
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "forge-admin", "version": "0.1.0"},
                },
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS},
            }
        elif method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool_call(tool_name, arguments)
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"unknown method: {method}"},
            }

        print(json.dumps(response))
        sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Forge admin MCP server")
    parser.add_argument("--list-tools", action="store_true", help="List available tools and exit")
    args = parser.parse_args()

    if args.list_tools:
        print(json.dumps(TOOLS, indent=2))
        return

    run_mcp_stdio()


if __name__ == "__main__":
    main()