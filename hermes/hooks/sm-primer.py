#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from common import debug, drop_noisy_autorecall_hits, emit_context, http_get, http_post, read_payload, rpc_call


def project_name(cwd: str) -> tuple[str, bool]:
    path = Path(cwd or ".").expanduser()
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], text=True, capture_output=True, timeout=2, check=False)
        root = Path(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else None
    except Exception:
        root = None
    if root and root != Path.home():
        return root.name, True
    return path.name or "workspace", False


def main() -> int:
    debug("on_session_start semantic-memory primer")
    payload = read_payload()
    cwd = str(payload.get("cwd") or payload.get("workspaceRoot") or Path.cwd())
    project, do_project = project_name(cwd)
    stats = http_post("/stats", {}, timeout=3.0) or rpc_call("sm_stats", {}, timeout=8)
    if not stats or stats.get("ok") is False:
        return 0
    facts = stats.get("facts", 0)
    docs = stats.get("documents", 0)
    chunks = stats.get("chunks", 0)
    edges = stats.get("graph_edges", 0)
    lines = [f"Persistent semantic memory is ACTIVE: {facts} facts, {docs} docs, {chunks} chunks, {edges} graph edges. This is shared long-term recall for Hermes."]
    integrity = http_get("/verify-integrity", timeout=3.0)
    if integrity and integrity.get("ok") and not integrity.get("integrity", True):
        issues = integrity.get("issues") or []
        lines.append("\nWARNING: semantic-memory integrity check reported issues: " + "; ".join(map(str, issues[:3])))
    if do_project:
        result = http_post("/search", {"query": f"{project} codebase project overview", "top_k": 5}, timeout=4.0) or rpc_call("sm_search", {"query": f"{project} codebase project overview", "top_k": 5}, timeout=8)
        hits = drop_noisy_autorecall_hits((result or {}).get("results") or [])
        if hits:
            key = "cosine_similarity" if any(h.get("cosine_similarity") is not None for h in hits) else "score"
            hits = sorted(hits, key=lambda h: float(h.get(key) or 0), reverse=True)
            top = float(hits[0].get(key) or 0)
            if (key == "cosine_similarity" and top >= 0.60) or (key == "score" and top > 0):
                lines.append(f"\nProject-scoped recall for {project} (verify against current code before relying):")
                for hit in hits[:3]:
                    content = " ".join(str(hit.get("content") or "").split())
                    if content:
                        lines.append("- " + (content[:300] + "..." if len(content) > 300 else content))
    lines.extend([
        "\n- RECALL: hooks auto-inject relevant memory; call sm_search/sm_list_facts/sm_get_fact_neighbors yourself when memory matters.",
        "- PERSIST: store only durable verified facts after dedupe; never store secrets, guesses, raw logs, or ephemeral conversation.",
        "- DISCIPLINE: current artifacts outrank memory; record corrections by append/supersede.",
    ])
    emit_context("on_session_start", "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
