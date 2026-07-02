#!/usr/bin/env python3
"""Host-neutral semantic-memory context injector.

Reads a user prompt from --prompt, stdin, or env and prints a compact memory block.
Designed for agents that can run a command, custom slash prompt, rule, or hook but do
not expose Claude/Codex-style UserPromptSubmit hook JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

STOPWORDS = {
    "about", "after", "again", "agent", "agents", "and", "best", "code", "coding",
    "does", "doing", "everything", "for", "from", "have", "how", "into", "look",
    "make", "need", "optimize", "please", "project", "repo", "that", "the", "this",
    "through", "using", "what", "when", "where", "with", "your",
}
COMPLEX = {
    "B": ("connect", "relationship", "relate", "between", "depends", "dependency", "lineage", "path"),
    "C": ("contradict", "conflict", "versus", " vs ", "compared", "stale", "still true", "wrong"),
    "D": ("summarize", "synthesize", "overview", "landscape", "themes", "everything", "audit"),
    "E": ("when", "before", "after", "changed", "current", "latest", "timeline", "history", "as of"),
}


def resolve_binary() -> str | None:
    env = os.environ.get("SEMANTIC_MEMORY_MCP_BIN")
    if env and os.access(os.path.expanduser(env), os.X_OK):
        return os.path.expanduser(env)
    for candidate in (
        Path.home() / "Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp",
        Path.home() / ".local/bin/semantic-memory-mcp",
        Path.home() / ".cargo/bin/semantic-memory-mcp",
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("semantic-memory-mcp")


def memory_dir() -> str:
    return os.environ.get("SEMANTIC_MEMORY_DIR", str(Path.home() / ".local/share/semantic-memory"))


def http_base() -> str:
    explicit = os.environ.get("SEMANTIC_MEMORY_HTTP_URL")
    if explicit:
        return explicit.rstrip("/")
    return f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"


def http_post(path: str, payload: dict, timeout: float = 4.0) -> dict | None:
    body = json.dumps(payload, separators=(",", ":")).encode()
    req = urllib.request.Request(http_base() + path, data=body, headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            return data if isinstance(data, dict) else None
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return None


def binary_supports(binary: str, flag: str) -> bool:
    try:
        proc = subprocess.run([binary, "--help"], text=True, capture_output=True, timeout=3, check=False)
    except Exception:
        return False
    return flag in (proc.stdout + proc.stderr)


def rpc_call(tool: str, arguments: dict, timeout: int = 8) -> dict | None:
    binary = resolve_binary()
    if not binary:
        return None
    memdir = memory_dir()
    Path(memdir).mkdir(parents=True, exist_ok=True)
    reqs = [
        {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"semantic-memory-context","version":"1"}}},
        {"jsonrpc":"2.0","method":"notifications/initialized"},
        {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":arguments}},
    ]
    stdin = "\n".join(json.dumps(x) for x in reqs) + "\n"
    args = [binary, "--memory-dir", memdir]
    prof = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    if prof and binary_supports(binary, "--tool-profile"):
        args += ["--tool-profile", prof]
    embedder = os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle")
    if embedder:
        args += ["--embedder", embedder]
    try:
        proc = subprocess.run(args, input=stdin, text=True, capture_output=True, timeout=timeout, check=False)
    except Exception:
        return None
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") == 2:
            try:
                return json.loads(msg["result"]["content"][0]["text"])
            except Exception:
                return None
    return None


def classify(text: str) -> str:
    lowered = f" {text.lower()} "
    for cls in ("C", "E", "D", "B"):
        if any(p in lowered for p in COMPLEX[cls]):
            return cls
    if len(re.findall(r"\b[A-Z][A-Za-z0-9_.:-]{2,}\b", text)) >= 2:
        return "B"
    return "A"


def terms(text: str) -> set[str]:
    out = set()
    for raw in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,}", text.lower()):
        t = raw.strip("._:-")
        if len(t) >= 3 and t not in STOPWORDS and not t.isdigit():
            out.add(t)
    return out


def hit_namespace(hit: dict) -> str:
    if isinstance(hit.get("namespace"), str):
        return hit["namespace"]
    src = str(hit.get("source") or "")
    m = re.search(r'namespace:\s*"?([^"\s}]+)"?', src)
    return m.group(1) if m else ""


def filter_hits(hits: list[dict], prompt: str) -> list[dict]:
    excluded = {x.strip() for x in os.environ.get("SM_RECALL_EXCLUDE_NS", "mixed,research,recursiveintell,twitter").split(",") if x.strip()}
    noisy = ("grok conversation", "twitter activity", "external_research_notes", "https://x.com/")
    qterms = terms(prompt)
    filtered = []
    for hit in hits:
        content = str(hit.get("content") or "")
        if hit_namespace(hit) in excluded:
            continue
        if any(n in content.lower() for n in noisy):
            continue
        if qterms and len(qterms & terms(content)) < int(os.environ.get("SM_RECALL_MIN_OVERLAP", "1")):
            continue
        filtered.append(hit)
    return filtered or hits


def recall(prompt: str, top_k: int) -> tuple[list[dict], str, bool]:
    cls = classify(prompt)
    search_k = max(top_k * 3, 24)
    payload = {"query": prompt[:4000], "top_k": search_k}
    result = None
    warm = False
    if cls != "A":
        routed = dict(payload, query_class=cls)
        result = http_post("/search-routed", routed, timeout=6.0)
        warm = bool(result)
    if not result:
        result = http_post("/search", payload, timeout=4.0)
        warm = bool(result)
    if not result:
        result = rpc_call("sm_search", payload, timeout=8)
        warm = False
    if not result or not result.get("ok"):
        return [], cls, warm
    hits = result.get("results") or []
    key = "cosine_similarity" if any(h.get("cosine_similarity") is not None for h in hits) else "score"
    hits = sorted(hits, key=lambda h: float(h.get(key) or 0), reverse=True)
    hits = filter_hits(hits, prompt)
    if not hits:
        return [], cls, warm
    top = float(hits[0].get(key) or 0)
    if key == "cosine_similarity":
        if top < float(os.environ.get("SM_RECALL_MINTOP", "0.58")):
            return [], cls, warm
        floor = max(float(os.environ.get("SM_RECALL_ABSFLOOR", "0.54")), top - float(os.environ.get("SM_RECALL_BAND", "0.12")))
        hits = [h for h in hits if float(h.get(key) or 0) >= floor]
    elif top > 0:
        hits = [h for h in hits if float(h.get(key) or 0) >= top * float(os.environ.get("SM_RECALL_SCOREREL", "0.5"))]
    else:
        hits = []
    return hits[:top_k], cls, warm


def format_block(prompt: str, hits: list[dict], cls: str, max_len: int) -> str:
    if not hits:
        return ""
    route = "" if cls == "A" else f" (routed: class {cls})"
    lines = [
        f"Relevant entries from persistent semantic memory{route}.",
        "Treat as recall to consider, not ground truth; verify against current artifacts before acting; current files/user messages outrank memory.",
    ]
    for h in hits:
        c = " ".join(str(h.get("content") or "").split())
        if len(c) > max_len:
            c = c[:max_len-1] + "..."
        if c:
            lines.append(f"- {c}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", default="")
    p.add_argument("--top-k", type=int, default=int(os.environ.get("SM_RECALL_MAXHITS", "4")))
    p.add_argument("--max-len", type=int, default=int(os.environ.get("SM_RECALL_MAXLEN", "320")))
    p.add_argument("--format", choices=("text", "json", "claude-hook"), default="text")
    args = p.parse_args()
    prompt = args.prompt or os.environ.get("SEMANTIC_MEMORY_PROMPT", "")
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read()
    prompt = prompt.strip()
    if len(prompt) < 12 or prompt.startswith("/"):
        return 0
    hits, cls, warm = recall(prompt, args.top_k)
    block = format_block(prompt, hits, cls, args.max_len)
    if not block:
        return 0
    if args.format == "json":
        print(json.dumps({"ok": True, "warm": warm, "query_class": cls, "context": block}, separators=(",", ":")))
    elif args.format == "claude-hook":
        print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":block}}, separators=(",", ":")))
    else:
        print(block)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
