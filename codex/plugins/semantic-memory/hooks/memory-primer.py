#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from common import debug, drop_superseded_hits, emit_context, read_payload, rpc_call


def project_name(cwd: str) -> tuple[str, bool]:
    path = Path(cwd or ".").expanduser()
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
        root = Path(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else None
    except Exception:
        root = None
    if root and root != Path.home():
        return root.name, True
    return path.name or "workspace", False


def main() -> int:
    debug("SessionStart semantic-memory primer")
    payload = read_payload()
    cwd = str(payload.get("cwd") or payload.get("workspaceRoot") or Path.cwd())
    project, do_project = project_name(cwd)
    stats = rpc_call("sm_stats", {}, timeout=8)
    if not stats or not stats.get("ok"):
        return 0
    lines = [
        "Persistent semantic memory is ACTIVE (semantic-memory MCP server): "
        f"{stats.get('facts', 0)} facts, {stats.get('documents', 0)} docs, "
        f"{stats.get('chunks', 0)} chunks, {stats.get('graph_edges', 0)} graph edges. "
        "This is shared long-term recall across Codex instances."
    ]
    if do_project:
        result = rpc_call("sm_search", {"query": f"{project} codebase project overview", "top_k": 10}, timeout=8)
        hits = sorted(
            (result or {}).get("results") or [],
            key=lambda item: float(item.get("cosine_similarity") or 0),
            reverse=True,
        )
        hits = drop_superseded_hits(hits, timeout=5)
        if hits and float(hits[0].get("cosine_similarity") or 0) >= 0.60:
            top = float(hits[0].get("cosine_similarity") or 0)
            kept = [hit for hit in hits if float(hit.get("cosine_similarity") or 0) >= max(0.56, top - 0.12)][:3]
            if kept:
                lines.append(f"\nProject-scoped recall for {project}; verify against current code before relying:")
                for hit in kept:
                    content = " ".join(str(hit.get("content") or "").split())
                    if len(content) > 300:
                        content = content[:299] + "..."
                    if content:
                        lines.append(f"- {content}")
    lines.extend(
        [
            "\n- RECALL: hooks auto-inject relevant memory, but call sm_search, sm_list_facts, or sm_get_fact_neighbors yourself when memory matters.",
            "- PERSIST: store durable verified facts with sm_add_fact after dedupe; use memory-capture for the disciplined write path.",
            "- DISCIPLINE: never let stored memory outrank current artifacts; record corrections by append/supersede.",
        ]
    )
    emit_context("SessionStart", "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
