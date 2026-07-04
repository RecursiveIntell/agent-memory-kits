#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from common import debug, http_post, read_payload


def main() -> int:
    debug("post_llm_call semantic-memory conversation capture")
    payload = read_payload()
    text = str(payload.get("response") or payload.get("assistant_response") or payload.get("content") or "")
    prompt = str(payload.get("prompt") or payload.get("user_prompt") or "")
    if len(text.strip()) < 20 and len(prompt.strip()) < 20:
        return 0
    session_id = str(payload.get("session_id") or payload.get("session") or "")
    digest = hashlib.sha256((session_id + "\n" + prompt[-1000:] + "\n" + text[-2000:]).encode("utf-8", "replace")).hexdigest()[:16]
    # Do not auto-promote conversation content as durable facts. This is an observation receipt only.
    summary = "Conversation turn receipt"
    if prompt:
        summary += f": user={prompt[:120]!r}"
    if text:
        summary += f" assistant={text[:160]!r}"
    summary += f" [sha256:{digest}]"
    if session_id:
        summary += f" (session: {session_id[:12]})"
    http_post("/add", {"content": summary, "namespace": "conversation-receipts", "source": "hermes-post-llm-call-hook"}, timeout=3.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
