#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def store_dir() -> Path:
    return Path(
        os.environ.get(
            "CONTEXT_GOVERNOR_STORE",
            str(Path.home() / ".hermes/context-governor"),
        )
    ).expanduser()


def crate_root() -> Path:
    return Path(
        os.environ.get(
            "CONTEXT_GOVERNOR_CRATE",
            str(Path.home() / "Coding/Libraries/context-governor"),
        )
    ).expanduser()


def resolve_binary() -> str | None:
    env = os.environ.get("CONTEXT_GOVERNOR_BIN")
    if env and os.access(os.path.expanduser(env), os.X_OK):
        return os.path.expanduser(env)
    for candidate in (
        crate_root() / "target/release/context-governor",
        Path.home() / ".local/bin/context-governor",
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "context-governor"


def run_cg(args: list[str], stdin: dict | None = None, timeout: int = 20) -> dict:
    binary = resolve_binary()
    if not binary:
        raise RuntimeError("context-governor binary not found")
    proc = subprocess.run(
        [binary, *args],
        input=json.dumps(stdin) if stdin is not None else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"context-governor exited {proc.returncode}")
    return json.loads(proc.stdout)


def text_result(payload: object) -> dict:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2, sort_keys=True),
            }
        ]
    }


def receipt_path(receipt_id: str, root: Path) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in receipt_id)
    return root / f"{safe}.json"


def tool_schemas() -> list[dict]:
    return [
        {
            "name": "cg_list_receipts",
            "description": "List stored context-governor receipt ids from the local receipt store.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "description": "Optional receipt store directory."}
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "cg_search",
            "description": "Search stored context-governor receipts and exact fallback content.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "default": 10},
                    "dir": {"type": "string", "description": "Optional receipt store directory."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cg_expand",
            "description": "Expand exact fallback content for a receipt item.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "receipt_id": {"type": "string"},
                    "item_id": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 1, "default": 100000},
                    "dir": {"type": "string", "description": "Optional receipt store directory."},
                },
                "required": ["receipt_id", "item_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cg_diff_receipt",
            "description": "Return context-governor diff counts and warnings for a stored receipt.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "receipt_id": {"type": "string"},
                    "dir": {"type": "string", "description": "Optional receipt store directory."},
                },
                "required": ["receipt_id"],
                "additionalProperties": False,
            },
        },
    ]


def call_tool(name: str, args: dict) -> dict:
    root = Path(args.get("dir") or store_dir()).expanduser()
    if name == "cg_list_receipts":
        receipts = sorted(path.stem for path in root.glob("*.json")) if root.exists() else []
        return text_result({"receipt_ids": receipts, "dir": str(root)})
    if name == "cg_search":
        return text_result(
            run_cg(
                [
                    "search",
                    "--dir",
                    str(root),
                    "--query",
                    str(args["query"]),
                    "--top-k",
                    str(int(args.get("top_k") or 10)),
                ]
            )
        )
    if name == "cg_expand":
        return text_result(
            run_cg(
                [
                    "expand",
                    "--dir",
                    str(root),
                    "--receipt",
                    str(args["receipt_id"]),
                    "--item",
                    str(args["item_id"]),
                    "--max-chars",
                    str(int(args.get("max_chars") or 100000)),
                ]
            )
        )
    if name == "cg_diff_receipt":
        path = receipt_path(str(args["receipt_id"]), root)
        response = json.loads(path.read_text(encoding="utf-8"))
        return text_result(run_cg(["diff"], stdin=response))
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
                "serverInfo": {"name": "context-governor", "version": "0.1.0"},
                "instructions": (
                    "Use context-governor tools to search and expand stored compaction "
                    "receipts. Treat summaries as background and expand exact fallback "
                    "when high-risk omitted context matters."
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
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }
        if response is not None:
            print(json.dumps(response, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
