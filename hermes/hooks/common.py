#!/usr/bin/env python3
from __future__ import annotations

import http.client
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from http_auth import authorization_headers


def debug(label: str) -> None:
    target = os.environ.get("SEMANTIC_MEMORY_HOOK_DEBUG")
    if not target:
        return
    try:
        with open(Path(target).expanduser(), "a", encoding="utf-8") as fh:
            fh.write(label + "\n")
    except Exception:
        pass


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
    return os.environ.get("SEMANTIC_MEMORY_DIR", str(Path.home() / ".hermes/semantic-memory.db"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_HTTP_OPENER = urllib.request.build_opener(_NoRedirect())


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def http_base() -> str | None:
    explicit = os.environ.get("SEMANTIC_MEMORY_HTTP_URL")
    if explicit:
        base = explicit.rstrip("/")
    else:
        port = os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", "1739")
        base = f"http://127.0.0.1:{port}"
    try:
        parsed = urllib.parse.urlsplit(base)
        hostname = parsed.hostname
        _ = parsed.port  # Force numeric/range validation.
    except ValueError:
        return None
    if not hostname or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if parsed.scheme == "http" and not _is_loopback_host(hostname):
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    return base


def http_get(path: str, timeout: float = 2.0) -> dict | None:
    headers = authorization_headers()
    base = http_base()
    if not headers or base is None:
        return None
    try:
        request = urllib.request.Request(base + path, headers=headers, method="GET")
        with _HTTP_OPENER.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        error.close()
        return None
    except (ValueError, http.client.InvalidURL, OSError, urllib.error.URLError, TimeoutError):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def http_post(path: str, payload: dict, timeout: float = 4.0) -> dict | None:
    headers = authorization_headers()
    base = http_base()
    if not headers or base is None:
        return None
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    try:
        request = urllib.request.Request(
            base + path,
            data=body,
            headers={"content-type": "application/json", **headers},
            method="POST",
        )
        with _HTTP_OPENER.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        error.close()
        return None
    except (ValueError, http.client.InvalidURL, OSError, urllib.error.URLError, TimeoutError):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _sanitized_child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("SEMANTIC_MEMORY_HTTP_TOKEN", None)
    env.pop("SM_BENCH_HTTP_AUTH_TOKEN", None)
    return env


def binary_help(binary: str) -> str:
    try:
        proc = subprocess.run(
            [binary, "--help"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
            env=_sanitized_child_env(),
        )
    except Exception:
        return ""
    return f"{proc.stdout}\n{proc.stderr}"


def rpc_call(tool: str, arguments: dict, timeout: int = 8) -> dict | None:
    binary = resolve_binary()
    if not binary:
        return None
    memdir = memory_dir()
    Path(memdir).mkdir(parents=True, exist_ok=True)
    reqs = [
        {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes-semantic-memory-hook","version":"1"}}},
        {"jsonrpc":"2.0","method":"notifications/initialized"},
        {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":arguments}},
    ]
    stdin = "\n".join(json.dumps(item) for item in reqs) + "\n"
    cmd = [binary, "--memory-dir", memdir]
    embedder = os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle")
    if embedder:
        cmd.extend(["--embedder", embedder])
    profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    if profile and "--tool-profile" in binary_help(binary):
        cmd.extend(["--tool-profile", profile])
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=_sanitized_child_env(),
        )
    except Exception:
        return None
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") != 2:
            continue
        try:
            return json.loads(msg["result"]["content"][0]["text"])
        except Exception:
            return None
    return None


def read_payload() -> dict:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def emit_context(event_name: str, text: str) -> None:
    """Emit Hermes' canonical shell-hook context envelope.

    ``agent.shell_hooks._parse_response`` accepts ``{"context": ...}`` for
    all non-tool events.  The former Claude Code ``hookSpecificOutput`` shape
    was silently discarded, making the primer and witnessed recall hooks inert
    even when retrieval succeeded.
    """
    _ = event_name  # retained for call-site readability and event tracing.
    print(json.dumps({"context": text}, separators=(",", ":")))


def hit_namespace(hit: dict) -> str:
    namespace = hit.get("namespace")
    if isinstance(namespace, str):
        return namespace
    source = str(hit.get("source") or "")
    if "namespace:" in source:
        return source.split("namespace:", 1)[1].split()[0].strip('"{}')
    return ""


def _ns_matches(pattern: str, namespace: str) -> bool:
    """Match a namespace against a pattern. Supports:
    - exact match: 'general'
    - prefix glob: 'hostile-*' matches 'hostile-benchmark-20260710'
    - prefix without glob: 'hostile' matches 'hostile-benchmark-20260710'
    """
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return namespace == prefix or namespace.startswith(prefix + ".")
    if pattern.endswith("*"):
        prefix = pattern[:-1]
        return namespace.startswith(prefix)
    return namespace == pattern


def drop_excluded_namespaces(hits: list[dict]) -> list[dict]:
    raw = os.environ.get("SM_RECALL_EXCLUDE_NS", "mixed,research,recursiveintell,twitter,hostile-*")
    patterns = [item.strip() for item in raw.split(",") if item.strip()]
    if not patterns:
        return hits
    return [
        hit for hit in hits
        if not any(_ns_matches(p, hit_namespace(hit)) for p in patterns)
    ]


def drop_noisy_autorecall_hits(hits: list[dict]) -> list[dict]:
    noisy = ("grok conversation", "twitter activity", "external_research_notes", "https://x.com/")
    return [hit for hit in hits if not any(marker in str(hit.get("content") or "").lower() for marker in noisy)]
