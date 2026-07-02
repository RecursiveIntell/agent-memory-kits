#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from common import debug, drop_superseded_hits, emit_context, http_post, read_payload, rpc_call


STOPWORDS = {
    "about", "after", "again", "agent", "agentic", "and", "best", "code",
    "coding", "does", "doing", "everything", "examine", "for", "from",
    "function", "have", "how", "improve", "into", "look", "looks", "make",
    "optimize", "perform", "performance", "possible", "research", "seem",
    "seems", "than", "that", "the", "this", "through", "using", "well",
    "what", "when", "where", "with", "your",
}


COMPLEXITY_PATTERNS = {
    "B": (
        "connect", "connected", "relationship", "relate", "between", "depends",
        "dependency", "lineage", "lead to", "led to", "path",
    ),
    "C": (
        "contradict", "conflict", "versus", " vs ", "compared", "stale",
        "still true", "is it true", "debunk", "wrong",
    ),
    "D": (
        "summarize", "synthesize", "overview", "landscape", "themes",
        "everything", "all about", "audit", "research",
    ),
    "E": (
        "when", "before", "after", "changed", "current", "latest", "timeline",
        "history", "as of", "updated",
    ),
}


def terms(text: str) -> set[str]:
    found = set()
    for raw in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,}", text.lower()):
        token = raw.strip("._:-")
        if len(token) < 3 or token in STOPWORDS or token.isdigit():
            continue
        found.add(token)
    return found


def classify_query(text: str) -> str:
    lowered = f" {text.lower()} "
    entity_like = len(re.findall(r"\b[A-Z][A-Za-z0-9_.:-]{2,}\b", text))
    if any(pattern in lowered for pattern in COMPLEXITY_PATTERNS["C"]):
        return "C"
    if any(pattern in lowered for pattern in COMPLEXITY_PATTERNS["E"]):
        return "E"
    if any(pattern in lowered for pattern in COMPLEXITY_PATTERNS["D"]):
        return "D"
    if entity_like >= 2 or any(pattern in lowered for pattern in COMPLEXITY_PATTERNS["B"]):
        return "B"
    return "A"


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "repo"


def git_root(cwd: str) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    root = Path(proc.stdout.strip()).resolve()
    if root == Path.home() or str(root) == "/":
        return None
    return root


def namespace_passes(prompt: str, cwd: str) -> list[list[str]]:
    passes: list[list[str]] = []
    root = git_root(cwd)
    if root:
        passes.append([f"code:{slug(root.name)}"])
    lowered = prompt.lower()
    if any(term in lowered for term in ("codex", "semantic-memory", "semantic memory", "mcp", "plugin", "hook", "ingest", "namespace", "memory")):
        passes.append(["codex", "infrastructure"])
    if any(term in lowered for term in ("project", "repo", "codebase", "architecture", "dependency", "component")):
        passes.append(["projects", "libraries", "codex"])
    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for group in passes:
        key = tuple(group)
        if key not in seen:
            seen.add(key)
            unique.append(group)
    return unique


def hit_namespace(hit: dict) -> str:
    namespace = hit.get("namespace")
    if isinstance(namespace, str):
        return namespace
    source = str(hit.get("source") or "")
    match = re.search(r'namespace:\s*"?([^"\s}]+)"?', source)
    return match.group(1) if match else ""


def drop_excluded_namespaces(hits: list[dict]) -> list[dict]:
    raw = os.environ.get("SM_RECALL_EXCLUDE_NS", "mixed,research,recursiveintell,twitter")
    excluded = {item.strip() for item in raw.split(",") if item.strip()}
    if not excluded:
        return hits
    kept = [hit for hit in hits if hit_namespace(hit) not in excluded]
    return kept


def drop_noisy_autorecall_hits(hits: list[dict]) -> list[dict]:
    noisy = (
        "grok conversation",
        "twitter activity",
        "external_research_notes",
        "https://x.com/",
    )
    return [
        hit
        for hit in hits
        if not any(marker in str(hit.get("content") or "").lower() for marker in noisy)
    ]


def warm_search(prompt: str, top_k: int, query_class: str, namespaces: list[str] | None = None) -> tuple[dict | None, bool]:
    payload = {"query": prompt, "top_k": top_k}
    if namespaces:
        payload["namespaces"] = namespaces
    if query_class == "A":
        result = http_post("/search", payload, timeout=4.0)
        return result, bool(result)
    routed_payload = dict(payload)
    routed_payload["query_class"] = query_class
    result = http_post(
        "/search-routed",
        routed_payload,
        timeout=6.0,
    )
    if result:
        return result, True
    result = http_post("/search", payload, timeout=4.0)
    return result, bool(result)


def stdio_search(prompt: str, top_k: int, namespaces: list[str] | None = None) -> dict | None:
    payload = {"query": prompt, "top_k": top_k}
    if namespaces:
        payload["namespaces"] = namespaces
    return rpc_call("sm_search", payload, timeout=8)


def prepare_hits(result: dict, warm: bool) -> tuple[list[dict], str]:
    results = result.get("results") or []
    score_key = "cosine_similarity" if any(hit.get("cosine_similarity") is not None for hit in results) else "score"
    hits = sorted(results, key=lambda item: float(item.get(score_key) or 0), reverse=True)
    hits = drop_superseded_hits(hits, timeout=5)
    hits = drop_excluded_namespaces(hits)
    hits = drop_noisy_autorecall_hits(hits)
    return hits, score_key


def merge_hits(existing: list[dict], incoming: list[dict], priority: int) -> list[dict]:
    seen = {hit.get("result_id") for hit in existing}
    merged = list(existing)
    for hit in incoming:
        result_id = hit.get("result_id")
        if result_id and result_id in seen:
            continue
        hit["_priority"] = priority
        seen.add(result_id)
        merged.append(hit)
    return merged


def freshness_rank(hit: dict) -> int:
    content = str(hit.get("content") or "")
    if "2026-06-27" in content:
        return 3
    if "2026-06-26" in content:
        return 2
    if "2026-06-24" in content or "2026-06-25" in content:
        return 1
    return 0


def main() -> int:
    payload = read_payload()
    prompt = str(payload.get("prompt") or payload.get("user_prompt") or "")
    if len(prompt) < 12 or prompt.lstrip().startswith("/"):
        return 0

    debug("UserPromptSubmit semantic-memory recall")
    cwd = str(payload.get("cwd") or payload.get("workspaceRoot") or Path.cwd())
    top_k = int(os.environ.get("SM_RECALL_TOPK", "8"))
    search_k = max(top_k * 3, 24)
    query_class = classify_query(prompt)
    result = None
    warm = False
    hits: list[dict] = []
    score_key = "score"
    for pass_index, namespaces in enumerate(namespace_passes(prompt, cwd)):
        scoped, scoped_warm = warm_search(prompt[:4000], search_k, query_class, namespaces=namespaces)
        if not scoped or not scoped.get("ok"):
            scoped = stdio_search(prompt[:4000], search_k, namespaces=namespaces)
            scoped_warm = False
        if scoped and scoped.get("ok"):
            scoped_hits, scoped_key = prepare_hits(scoped, scoped_warm)
            hits = merge_hits(hits, scoped_hits, pass_index)
            score_key = scoped_key
            warm = warm or scoped_warm
    result, broad_warm = warm_search(prompt[:4000], search_k, query_class)
    if not result:
        result = stdio_search(prompt[:4000], search_k)
        broad_warm = False
    if not result or not result.get("ok"):
        if not hits:
            return 0
    else:
        broad_hits, broad_key = prepare_hits(result, broad_warm)
        hits = merge_hits(hits, broad_hits, 50)
        score_key = broad_key
        warm = warm or broad_warm

    if not hits and warm and query_class != "A":
        fallback = stdio_search(prompt[:4000], search_k)
        if fallback and fallback.get("ok"):
            fallback_hits, score_key = prepare_hits(fallback, False)
            hits = merge_hits(hits, fallback_hits, 100)
    if not hits:
        return 0

    query_terms = terms(prompt)
    min_overlap = int(os.environ.get("SM_RECALL_MIN_OVERLAP", "1"))
    if query_terms and min_overlap > 0 and warm and query_class != "A":
        has_overlap = any(
            len(query_terms & terms(str(hit.get("content") or ""))) >= min_overlap
            for hit in hits
        )
        if not has_overlap:
            fallback = rpc_call("sm_search", {"query": prompt[:4000], "top_k": search_k}, timeout=8)
            if fallback and fallback.get("ok"):
                fallback_hits, score_key = prepare_hits(fallback, False)
                hits = merge_hits([], fallback_hits, 100)

    hits = sorted(
        hits,
        key=lambda item: (
            int(item.get("_priority") or 0),
            -freshness_rank(item),
            -float(item.get(score_key) or 0),
        ),
    )

    mintop = float(os.environ.get("SM_RECALL_MINTOP", "0.58"))
    band = float(os.environ.get("SM_RECALL_BAND", "0.12"))
    absfloor = float(os.environ.get("SM_RECALL_ABSFLOOR", "0.54"))
    scorerel = float(os.environ.get("SM_RECALL_SCOREREL", "0.5"))
    max_hits = int(os.environ.get("SM_RECALL_MAXHITS", "4"))
    max_len = int(os.environ.get("SM_RECALL_MAXLEN", "320"))

    top = float(hits[0].get(score_key) or 0)
    if score_key == "cosine_similarity":
        if top < mintop:
            return 0
        floor = max(absfloor, top - band)
        kept = [hit for hit in hits if float(hit.get(score_key) or 0) >= floor][:max_hits]
    else:
        if top <= 0:
            return 0
        kept = [hit for hit in hits if float(hit.get(score_key) or 0) >= top * scorerel][:max_hits]
    if query_terms and min_overlap > 0:
        overlapped = [
            hit
            for hit in kept
            if len(query_terms & terms(str(hit.get("content") or ""))) >= min_overlap
        ]
        if not overlapped:
            fallback = stdio_search(prompt[:4000], search_k)
            if fallback and fallback.get("ok"):
                fallback_hits, score_key = prepare_hits(fallback, False)
                hits = merge_hits([], fallback_hits, 100)
                if not hits:
                    return 0
                top = float(hits[0].get(score_key) or 0)
                if score_key == "cosine_similarity":
                    if top < mintop:
                        return 0
                    floor = max(absfloor, top - band)
                    kept = [hit for hit in hits if float(hit.get(score_key) or 0) >= floor][:max_hits]
                else:
                    if top <= 0:
                        return 0
                    kept = [hit for hit in hits if float(hit.get(score_key) or 0) >= top * scorerel][:max_hits]
                overlapped = [
                    hit
                    for hit in kept
                    if len(query_terms & terms(str(hit.get("content") or ""))) >= min_overlap
                ]
            if not overlapped:
                return 0
        kept = overlapped
    lines = []
    for hit in kept:
        content = " ".join(str(hit.get("content") or "").split())
        if len(content) > max_len:
            content = content[: max_len - 1] + "..."
        if content:
            lines.append(f"- {content}")
    if not lines:
        return 0

    route_note = "" if query_class == "A" else f" (routed: class {query_class})"
    header = (
        f"Relevant entries from persistent semantic memory, auto-retrieved for this prompt{route_note}. "
        "Treat as recall to consider, not ground truth; verify against current artifacts before acting, "
        "and never let memory outrank current sources:"
    )
    emit_context("UserPromptSubmit", header + "\n" + "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
