#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

from common import debug, http_post, read_payload, repository_namespace, rpc_call  # noqa: E402


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
        "everything", "all about", "audit", "research", "refactor", "review",
        "implement", "fix", "debug",
    ),
    "E": (
        "when", "before", "after", "changed", "current", "latest", "timeline",
        "history", "as of", "updated",
    ),
}

IGNORE_ROOTS = {str(Path.home()), "/", "/tmp"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "repo"


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
    if str(root) in IGNORE_ROOTS:
        return None
    return root


def git_head(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def git_file_count(root: Path) -> int:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return 0
    if proc.returncode != 0:
        return 0
    return sum(1 for line in proc.stdout.splitlines() if line.strip())


def manifest_count(root: Path) -> int:
    names = {
        "Cargo.toml", "package.json", "pyproject.toml", "go.mod", "pom.xml",
        "composer.json", "build.gradle", "build.gradle.kts", "Gemfile",
        "pubspec.yaml", "mix.exs", "CMakeLists.txt", "Package.swift",
        "setup.py", "requirements.txt",
    }
    found = 0
    for current, dirs, files in os.walk(root):
        dirs[:] = [
            d for d in dirs
            if d not in {".git", "node_modules", "target", "dist", "build", ".venv", "venv", "vendor"}
            and not d.startswith(".")
        ]
        found += sum(1 for name in files if name in names or name.endswith(".csproj"))
        if found >= 3:
            break
    return found


def cache_dir() -> Path:
    base = os.environ.get("SM_AUTO_INGEST_STATE_DIR")
    return Path(base).expanduser() if base else Path.home() / ".cache/semantic-memory/auto-ingest"


def stamp_paths(root: Path) -> tuple[Path, Path, Path]:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    base = cache_dir()
    return base / f"{digest}.json", base / f"{digest}.lock", base / f"{digest}.log"


def already_current(stamp: Path, head: str, ttl_seconds: int) -> bool:
    try:
        data = json.loads(stamp.read_text(encoding="utf-8"))
    except Exception:
        return False
    if data.get("head") and head and data.get("head") == head:
        return True
    last = float(data.get("started_at") or 0)
    return bool(last and time.time() - last < ttl_seconds)


def namespace_has_coverage(namespace: str, query: str) -> bool:
    result = rpc_call(
        "sm_search_witnessed",
        {"query": query[:4000], "namespaces": [namespace], "top_k": 3},
        timeout=6,
    )
    if not result or not result.get("ok"):
        return False
    return bool(result.get("results"))


def routing_confirms_complexity(prompt: str, query_class: str) -> bool:
    if query_class == "A":
        return False
    routed = http_post(
        "/search-routed",
        {"query": prompt[:4000], "top_k": 1, "query_class": query_class},
        timeout=3.0,
    )
    return routed is None or bool(routed.get("ok"))


def spawn_ingest(root: Path, namespace: str, stamp: Path, lock: Path, log: Path, head: str, file_count: int, query_class: str) -> None:
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock_ttl = int(os.environ.get("SM_AUTO_INGEST_LOCK_TTL_SECONDS", str(2 * 3600)))
    if lock.exists():
        try:
            if time.time() - lock.stat().st_mtime > lock_ttl:
                lock.unlink()
        except Exception:
            pass
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))

    stamp.write_text(
        json.dumps(
            {
                "root": str(root),
                "namespace": namespace,
                "head": head,
                "file_count": file_count,
                "query_class": query_class,
                "started_at": time.time(),
                "status": "started",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[1] / "scripts/ingest_codebase.py"
    max_components = os.environ.get("SM_AUTO_INGEST_MAX_COMPONENTS", "400")
    cmd = [
        sys.executable,
        str(script),
        "--path",
        str(root),
        "--namespace",
        namespace,
        "--dedupe",
        "--max-components",
        max_components,
    ]
    runner = (
        "import json, os, subprocess, sys, time\n"
        "lock=sys.argv[1]; stamp=sys.argv[2]; cmd=sys.argv[3:]\n"
        "rc=1\n"
        "try:\n"
        "    rc=subprocess.call(cmd)\n"
        "    try:\n"
        "        data=json.loads(open(stamp, encoding='utf-8').read())\n"
        "    except Exception:\n"
        "        data={}\n"
        "    data.update({'finished_at': time.time(), 'status': 'ok' if rc == 0 else 'failed', 'returncode': rc})\n"
        "    open(stamp, 'w', encoding='utf-8').write(json.dumps(data, indent=2) + '\\n')\n"
        "finally:\n"
        "    try: os.unlink(lock)\n"
        "    except FileNotFoundError: pass\n"
        "sys.exit(rc)\n"
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"\n--- auto-ingest {time.strftime('%Y-%m-%dT%H:%M:%S%z')} {root} {namespace} ---\n")
        subprocess.Popen(
            [sys.executable, "-c", runner, str(lock), str(stamp), *cmd],
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )


def main() -> int:
    if os.environ.get("SM_AUTO_INGEST", "0").lower() not in {"1", "true", "yes", "on"}:
        return 0
    payload = read_payload()
    prompt = str(payload.get("prompt") or payload.get("user_prompt") or "")
    if len(prompt) < int(os.environ.get("SM_AUTO_INGEST_MIN_PROMPT", "24")) or prompt.lstrip().startswith("/"):
        return 0

    query_class = classify_query(prompt)
    if query_class == "A":
        return 0
    if not routing_confirms_complexity(prompt, query_class):
        return 0

    cwd = str(payload.get("cwd") or payload.get("workspaceRoot") or Path.cwd())
    root = git_root(cwd)
    if not root:
        return 0

    file_count = git_file_count(root)
    min_files = int(os.environ.get("SM_AUTO_INGEST_MIN_FILES", "120"))
    min_manifests = int(os.environ.get("SM_AUTO_INGEST_MIN_MANIFESTS", "2"))
    manifests = manifest_count(root)
    if file_count < min_files and manifests < min_manifests:
        return 0

    explicit_namespace = os.environ.get("SM_AUTO_INGEST_NAMESPACE")
    namespace = explicit_namespace or repository_namespace(root)
    if namespace_has_coverage(namespace, f"{root.name} codebase project overview"):
        return 0

    head = git_head(root)
    stamp, lock, log = stamp_paths(root)
    ttl = int(os.environ.get("SM_AUTO_INGEST_TTL_SECONDS", str(24 * 3600)))
    if already_current(stamp, head, ttl):
        return 0

    debug(f"auto-ingest spawning for {root} namespace={namespace} class={query_class}")
    spawn_ingest(root, namespace, stamp, lock, log, head, file_count, query_class)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
