#!/usr/bin/env python3
"""Hostile audit script — cross-checks a captured fact with a second LLM before promotion.

Usage:
    python hostile-audit.py --fact-json '{"claim": "..."}' [--auditor-url URL] [--auditor-model MODEL] [--fact-id ID]

Emits a HostileAuditResultV1 JSON to stdout.
Fails open (valid=null, exit 0) if the auditor is unreachable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4

SCHEMA = "HostileAuditResultV1"
DEFAULT_AUDITOR_URL = os.environ.get("RI_AUDITOR_URL", "http://localhost:8081")
DEFAULT_AUDITOR_MODEL = os.environ.get("RI_AUDITOR_MODEL", "llama3")
HTTP_TIMEOUT = 10  # seconds


def _parse_json_object(text: str) -> dict | None:
    """Find and parse the first JSON object in *text*.

    Looks for the first ``{...}`` substring that parses as valid JSON.
    Returns the parsed dict or None if nothing usable is found.
    """
    # Try the whole text first (best case: model obeyed "ONLY JSON").
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # Scan for brace-delimited JSON objects, progressively.
    start = 0
    while True:
        open_idx = text.find("{", start)
        if open_idx == -1:
            return None
        # Find matching close brace by scanning forward.
        depth = 0
        for i in range(open_idx, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[open_idx : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break  # try next open brace
        start = open_idx + 1


def _call_auditor(url: str, model: str, prompt: str) -> dict | None:
    """POST an Ollama-style /generate request to *url*. Returns parsed JSON dict or None."""
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    # Ollama-style endpoint
    full_url = url.rstrip("/") + "/api/generate"
    req = urllib.request.Request(
        full_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None

    # Ollama /generate returns {"response": "...", ...}
    try:
        outer = json.loads(body)
        if isinstance(outer, dict) and "response" in outer:
            inner_text = outer["response"]
            parsed = _parse_json_object(inner_text)
            if parsed is not None:
                return parsed
            # Maybe the whole body is just text
            return _parse_json_object(body)
        # If the outer body itself looks like our target dict
        if isinstance(outer, dict) and ("valid" in outer or "reason" in outer):
            return outer
    except (json.JSONDecodeError, ValueError):
        pass

    return _parse_json_object(body)


def _emit_result(
    fact_id: str | None,
    auditor_model: str,
    valid: bool | None,
    reason: str,
    trace_id: str,
) -> dict:
    result = {
        "schema": SCHEMA,
        "fact_id": fact_id,
        "auditor_model": auditor_model,
        "valid": valid,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
    }
    print(json.dumps(result))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hostile audit of a captured fact")
    parser.add_argument("--fact-json", required=True, help="JSON string with the fact content to verify")
    parser.add_argument(
        "--auditor-url",
        default=DEFAULT_AUDITOR_URL,
        help="Auditor LLM endpoint (default: $RI_AUDITOR_URL or http://localhost:8081)",
    )
    parser.add_argument(
        "--auditor-model",
        default=DEFAULT_AUDITOR_MODEL,
        help="Auditor model name (default: $RI_AUDITOR_MODEL or llama3)",
    )
    parser.add_argument("--fact-id", default=None, help="Optional fact ID being audited")
    args = parser.parse_args(argv)

    trace_id = f"trace:hostile-audit:{uuid4().hex}"

    # Parse the fact JSON to get the content to verify.
    try:
        fact_data = json.loads(args.fact_json)
    except (json.JSONDecodeError, ValueError):
        _emit_result(args.fact_id, args.auditor_model, None, "invalid fact-json input", trace_id)
        return 0

    # The content to verify: use "content" or "claim" key, or the raw string.
    if isinstance(fact_data, dict):
        fact_content = fact_data.get("content") or fact_data.get("claim") or json.dumps(fact_data)
    elif isinstance(fact_data, str):
        fact_content = fact_data
    else:
        fact_content = str(fact_data)

    prompt = (
        'Verify this claim against your knowledge. Is it accurate? '
        'Reply ONLY with JSON: {"valid": true/false, "reason": "brief explanation"}. '
        f'Claim: {fact_content}'
    )

    auditor_response = _call_auditor(args.auditor_url, args.auditor_model, prompt)

    if auditor_response is None:
        # Fail open: auditor unavailable
        _emit_result(args.fact_id, args.auditor_model, None, "auditor unavailable", trace_id)
        return 0

    valid_raw = auditor_response.get("valid")
    reason = auditor_response.get("reason", "")

    # Coerce valid to bool or None
    if isinstance(valid_raw, bool):
        valid = valid_raw
    elif isinstance(valid_raw, str):
        valid_lower = valid_raw.strip().lower()
        if valid_lower in ("true", "1", "yes"):
            valid = True
        elif valid_lower in ("false", "0", "no"):
            valid = False
        else:
            valid = None
    else:
        valid = None

    _emit_result(args.fact_id, args.auditor_model, valid, reason, trace_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())