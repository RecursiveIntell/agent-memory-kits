#!/usr/bin/env python3
"""ClaimLedger MCP server for agent kits.

Exposes claim/evidence/provenance tools via stdio JSON-RPC.
Wraps the claim-ledger CLI binary.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_binary() -> str | None:
    env = os.environ.get("CLAIM_LEDGER_BIN")
    if env and os.access(os.path.expanduser(env), os.X_OK):
        return os.path.expanduser(env)
    for c in (
        Path.home() / "Coding/Libraries/claim-ledger/target/release/claim-ledger",
        Path.home() / ".local/bin/claim-ledger",
        Path.home() / ".cargo/bin/claim-ledger",
    ):
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return shutil.which("claim-ledger")


def run_cli(args: list[str], stdin: str | None = None, timeout: int = 30) -> dict:
    binary = resolve_binary()
    if not binary:
        raise RuntimeError("claim-ledger binary not found")
    proc = subprocess.run(
        [binary, *args],
        input=stdin,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"claim-ledger exited {proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"stdout": proc.stdout, "stderr": proc.stderr}


def text_result(payload: object) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}]}


def tool_schemas() -> list[dict]:
    return [
        {
            "name": "cl_inspect",
            "description": "Inspect a ClaimLedger claims JSONL file and return summary statistics.",
            "inputSchema": {
                "type": "object",
                "properties": {"claims_jsonl": {"type": "string", "description": "Path to claims JSONL file"}},
                "required": ["claims_jsonl"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cl_validate",
            "description": "Validate a ClaimLedger output directory for integrity and digest chain correctness.",
            "inputSchema": {
                "type": "object",
                "properties": {"out_dir": {"type": "string", "description": "Path to ClaimLedger output directory"}},
                "required": ["out_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cl_export_bundle",
            "description": "Export a generic app-agnostic ClaimLedger bundle from an output directory.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "out_dir": {"type": "string", "description": "Path to ClaimLedger output directory"},
                    "bundle_out": {"type": "string", "description": "Path for bundle output file"},
                },
                "required": ["out_dir", "bundle_out"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cl_ledger_verify",
            "description": "Verify the append-only JSONL ledger digest chain for tamper detection.",
            "inputSchema": {
                "type": "object",
                "properties": {"ledger_path": {"type": "string", "description": "Path to ledger JSONL file"}},
                "required": ["ledger_path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cl_run",
            "description": "Run the full ClaimLedger P0 pipeline on a directory, producing claims, evidence, and receipts.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory or file to process"},
                    "out_dir": {"type": "string", "description": "Output directory (optional)"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    ]


def call_tool(name: str, args: dict) -> dict:
    if name == "cl_inspect":
        return text_result(run_cli(["inspect", str(args["claims_jsonl"])]))
    if name == "cl_validate":
        return text_result(run_cli(["validate", str(args["out_dir"])]))
    if name == "cl_export_bundle":
        return text_result(run_cli(["export-bundle", str(args["out_dir"]), "--bundle-out", str(args["bundle_out"])]))
    if name == "cl_ledger_verify":
        return text_result(run_cli(["ledger-verify", str(args["ledger_path"])]))
    if name == "cl_run":
        cmd = ["run", str(args["path"])]
        if "out_dir" in args:
            cmd.extend(["--out", str(args["out_dir"])])
        return text_result(run_cli(cmd, timeout=60))
    raise RuntimeError(f"unknown tool: {name}")


def handle(request: dict) -> dict | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "claim-ledger", "version": "0.1.0"},
                "instructions": (
                    "Use ClaimLedger tools to create, inspect, and verify claim/evidence/provenance receipts. "
                    "Every material agent assertion should be backed by a claim with evidence. "
                    "Receipts prove provenance, not task success."
                ),
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tool_schemas()}}
    if method == "tools/call":
        params = request.get("params") or {}
        try:
            result = call_tool(str(params.get("name")), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except Exception:
            continue
        response = handle(request)
        if response is not None:
            print(json.dumps(response), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
