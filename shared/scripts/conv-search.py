#!/usr/bin/env python3
"""sm-conv-search — search past conversation messages via the semantic-memory HTTP server.

Tries the warm HTTP server first (SEMANTIC_MEMORY_HTTP_PORT, default 1739).
Falls back to stdio MCP sm_search_conversations if the HTTP endpoint is unavailable.

Usage:
  sm-conv-search "what did we discuss about hooks?"
  echo "Rust crate dependencies" | sm-conv-search
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

DEFAULT_PORT = 1739
HTTP_TIMEOUT = 5  # seconds


def search_http(query: str, port: int) -> list[dict] | None:
    """Attempt to query the warm HTTP server. Returns results or None on failure."""
    url = f"http://127.0.0.1:{port}/search-conversations"
    payload = json.dumps({"query": query}).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data if isinstance(data, list) else []
    except (URLError, HTTPError, ConnectionError, OSError, json.JSONDecodeError):
        return None


def search_stdio_mcp(query: str) -> list[dict]:
    """Fall back to stdio MCP sm_search_conversations."""
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "sm-conv-search", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "sm_search_conversations",
                    "arguments": {"query": query}}},
    ]
    proc = subprocess.run(
        ["semantic-memory-mcp"],
        input="\n".join(json.dumps(r) for r in reqs) + "\n",
        text=True, capture_output=True, timeout=30, check=False,
    )
    if proc.returncode != 0:
        print(f"ERROR: semantic-memory-mcp exited {proc.returncode}", file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        return []
    results = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == 2:
            result = msg.get("result", {})
            content = result.get("content", [])
            for item in content:
                if item.get("type") == "text":
                    try:
                        parsed = json.loads(item["text"])
                        if isinstance(parsed, list):
                            results.extend(parsed)
                        elif isinstance(parsed, dict) and "results" in parsed:
                            results.extend(parsed["results"])
                    except (json.JSONDecodeError, KeyError):
                        pass
    return results


def format_results(results: list[dict]) -> str:
    if not results:
        return "No conversation results found.\n"
    lines = []
    lines.append(f"{'='*70}")
    lines.append(f"  Conversation Search Results ({len(results)} hits)")
    lines.append(f"{'='*70}")
    for i, r in enumerate(results, 1):
        session_id = r.get("session_id", "unknown")
        timestamp = r.get("timestamp", r.get("ts", ""))
        role = r.get("role", "")
        score = r.get("score", "")
        snippet = r.get("content", r.get("snippet", r.get("text", "")))
        if len(snippet) > 300:
            snippet = snippet[:297] + "..."
        lines.append(f"\n─[{i}]─────────────────────────────────────────────")
        lines.append(f"  session:  {session_id}")
        if timestamp:
            lines.append(f"  time:     {timestamp}")
        if role:
            lines.append(f"  role:     {role}")
        if score:
            lines.append(f"  score:    {score}")
        lines.append(f"  snippet:  {snippet}")
    lines.append(f"\n{'='*70}")
    return "\n".join(lines) + "\n"


def main() -> int:
    # Get query from arg or stdin
    query = ""
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        query = sys.stdin.read().strip()

    if not query:
        print("Usage: sm-conv-search <query>", file=sys.stderr)
        print("       echo <query> | sm-conv-search", file=sys.stderr)
        return 2

    port = int(os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", str(DEFAULT_PORT)))

    # Try HTTP first
    results = search_http(query, port)
    if results is not None:
        print(f"(via HTTP :{port})", file=sys.stderr)
        print(format_results(results))
        return 0

    # Fall back to stdio MCP
    print(f"(HTTP :{port} unavailable — falling back to stdio MCP)", file=sys.stderr)
    results = search_stdio_mcp(query)
    print(format_results(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())