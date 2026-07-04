#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(os.environ.get("SEMANTIC_MEMORY_DIR", Path.home() / ".local/share/semantic-memory")).expanduser()
HTTP_URL = os.environ.get("SEMANTIC_MEMORY_HTTP_URL") or f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"
CG_STORE = Path(os.environ.get("CONTEXT_GOVERNOR_STORE", Path.home() / ".local/share/context-governor/receipts")).expanduser()

RESULTS: list[dict] = []
ROOT = Path(__file__).resolve().parents[2]


def record(status: str, label: str, detail: str = "") -> None:
    RESULTS.append({"status": status, "label": label, "detail": detail})
    print(f"{status:<4} {label}{': ' + detail if detail else ''}")


def ok(label: str, detail: str = "") -> None: record("OK", label, detail)
def warn(label: str, detail: str = "") -> None: record("WARN", label, detail)
def fail(label: str, detail: str = "") -> None: record("FAIL", label, detail)


def resolve_semantic_binary() -> Path | None:
    candidates: list[Path] = []
    env = os.environ.get("SEMANTIC_MEMORY_MCP_BIN")
    if env: candidates.append(Path(env).expanduser())
    candidates.extend([
        Path.home() / "Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp",
        Path.home() / ".local/bin/semantic-memory-mcp",
    ])
    if which := shutil.which("semantic-memory-mcp"):
        candidates.append(Path(which))
    candidates.append(Path.home() / ".cargo/bin/semantic-memory-mcp")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK): return candidate
    return None


def resolve_cg_binary() -> Path | None:
    candidates: list[Path] = []
    env = os.environ.get("CONTEXT_GOVERNOR_BIN")
    if env: candidates.append(Path(env).expanduser())
    candidates.extend([
        Path.home() / "Coding/Libraries/context-governor/target/release/context-governor",
        Path.home() / ".local/bin/context-governor",
    ])
    if which := shutil.which("context-governor"):
        candidates.append(Path(which))
    candidates.append(Path.home() / ".cargo/bin/context-governor")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK): return candidate
    return None


def binary_help(binary: Path) -> str:
    try:
        proc = subprocess.run([str(binary), "--help"], text=True, capture_output=True, timeout=5, check=False)
    except Exception as exc:
        fail("binary --help", str(exc)); return ""
    if proc.returncode == 0: ok("binary --help", str(binary))
    else: warn("binary --help", proc.stderr.strip()[-300:])
    return f"{proc.stdout}\n{proc.stderr}"


def http_get(path: str, label: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(HTTP_URL.rstrip("/") + path, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        data = json.loads(raw)
        ok(label, f"{HTTP_URL}{path} {str(data)[:300]}")
        return data if isinstance(data, dict) else None
    except Exception as exc:
        warn(label, f"{HTTP_URL}{path} unavailable ({exc})")
        return None


def rpc_tools_list(binary: Path) -> bool:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    reqs = [
        {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"semantic-memory-agent-kit-doctor","version":"1"}}},
        {"jsonrpc":"2.0","method":"notifications/initialized"},
        {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}},
    ]
    stdin = "\n".join(json.dumps(x) for x in reqs) + "\n"
    cmd = [str(binary), "--memory-dir", str(MEMORY_DIR), "--embedder", os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle")]
    help_text = binary_help(binary)
    profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    if "--tool-profile" in help_text and profile: cmd.extend(["--tool-profile", profile])
    try:
        proc = subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=25, check=False)
    except Exception as exc:
        fail("semantic-memory MCP tools/list", str(exc)); return False
    for line in proc.stdout.splitlines():
        try: msg = json.loads(line)
        except Exception: continue
        if msg.get("id") == 2:
            tools = msg.get("result", {}).get("tools", [])
            names = {t.get("name") for t in tools}
            required = {"sm_search", "sm_add_fact", "sm_stats", "sm_supersede_fact"}
            missing = sorted(required - names)
            if missing:
                fail("semantic-memory MCP tools/list", "missing " + ", ".join(missing)); return False
            ok("semantic-memory MCP tools/list", f"{len(tools)} tools exposed; required tools present")
            return True
    fail("semantic-memory MCP tools/list", (proc.stderr or proc.stdout)[-500:].strip()); return False


def cg_mcp_tools_list() -> bool:
    script = Path(__file__).resolve().parent / "context-governor-mcp.py"
    reqs = [
        {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"semantic-memory-agent-kit-doctor","version":"1"}}},
        {"jsonrpc":"2.0","method":"notifications/initialized"},
        {"jsonrpc":"2.0","id":2,"method":"tools/list"},
    ]
    try:
        proc = subprocess.run([str(script)], input="\n".join(json.dumps(x) for x in reqs)+"\n", text=True, capture_output=True, timeout=15, check=False)
    except Exception as exc:
        fail("context-governor MCP tools/list", str(exc)); return False
    if proc.returncode != 0:
        fail("context-governor MCP tools/list", proc.stderr.strip()[-500:]); return False
    for line in proc.stdout.splitlines():
        try: msg=json.loads(line)
        except Exception: continue
        if msg.get("id") == 2:
            tools=msg.get("result",{}).get("tools",[]); names={t.get("name") for t in tools}
            required={"cg_list_receipts","cg_search","cg_expand","cg_diff_receipt"}
            missing=sorted(required-names)
            if missing: fail("context-governor MCP tools/list", "missing "+", ".join(missing)); return False
            ok("context-governor MCP tools/list", f"{len(tools)} tools exposed; required tools present")
            return True
    fail("context-governor MCP tools/list", (proc.stderr or proc.stdout)[-500:].strip()); return False


def cg_status(binary: Path | None) -> None:
    CG_STORE.mkdir(parents=True, exist_ok=True)
    ok("context-governor receipt store", str(CG_STORE))
    if not binary:
        fail("context-governor binary", "not found; run shared/scripts/install_context_governor.sh")
        return
    ok("context-governor binary", str(binary))
    try:
        proc = subprocess.run([str(binary), "status", "--dir", str(CG_STORE)], text=True, capture_output=True, timeout=10, check=False)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            ok("context-governor status", f"receipts={data.get('receipt_count')} bytes={data.get('total_bytes')}")
        else:
            warn("context-governor status", proc.stderr.strip()[-300:])
    except Exception as exc:
        warn("context-governor status", str(exc))


def compact_smoke() -> None:
    script = Path(__file__).resolve().parent / "context-governor-compact.py"
    payload = {"messages":[{"role":"user","content":"Doctor deep smoke: preserve /tmp/file and failing test receipt."},{"role":"assistant","content":"Verification command exited 0 and receipt path will be stored."}]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh); tmp = fh.name
    try:
        proc = subprocess.run([str(script), "--input", tmp, "--session-id", "doctor-deep-smoke"], text=True, capture_output=True, timeout=45, check=False)
        if proc.returncode == 0: ok("context-governor compact smoke", proc.stdout.splitlines()[0] if proc.stdout else "ok")
        else: fail("context-governor compact smoke", proc.stderr.strip()[-500:])
    finally:
        Path(tmp).unlink(missing_ok=True)


def config_paths() -> None:
    paths = [
        Path.home()/"Documents/Cline/Rules/semantic-memory.md",
        Path.home()/".roo/rules/semantic-memory.md",
        Path.home()/".codeium/windsurf/memories/global_rules.md",
        Path.home()/".continue/rules/semantic-memory.md",
        Path.home()/".continue/config.yaml",
        Path.home()/".config/opencode/AGENTS.md",
        Path.home()/".config/opencode/commands/semantic-memory-recall.md",
    ]
    for p in paths:
        (ok if p.exists() else warn)("config path", str(p) + (" exists" if p.exists() else " missing"))


def hook_manifest_paths(host: str) -> None:
    """Validate Tier-0 plugin manifests do not point at missing hook files."""
    hosts = ["hermes"] if host in {"all", "hermes"} else []
    for name in hosts:
        manifest = ROOT / name / "plugin.json"
        if not manifest.exists():
            warn("hook manifest", f"{manifest} missing")
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            fail("hook manifest", f"{manifest}: invalid JSON: {exc}")
            continue
        host_cfg = data.get(name) if isinstance(data.get(name), dict) else None
        hooks = ((host_cfg or data.get("hermes") or {}).get("hooks") or {})
        if not isinstance(hooks, dict):
            warn("hook manifest", f"{manifest}: no hooks object")
            continue
        missing = []
        nonexec = []
        for event, rel in hooks.items():
            path = manifest.parent / str(rel)
            if not path.exists():
                missing.append(f"{event}:{rel}")
            elif path.suffix in {".sh", ".bash", ".py"} and not os.access(path, os.X_OK):
                nonexec.append(f"{event}:{rel}")
        if missing:
            fail("hook manifest paths", "; ".join(missing))
        elif nonexec:
            fail("hook manifest executability", "; ".join(nonexec))
        else:
            ok("hook manifest paths", f"{manifest}: {len(hooks)} hook file(s) present and executable")


def claim_ledger_check() -> None:
    """Check if claim-ledger companion MCP is reachable and responds to tools/list."""
    script = ROOT / "shared" / "scripts" / "claim-ledger-mcp.py"
    if not script.exists():
        script = Path(__file__).resolve().parent / "claim-ledger-mcp.py"
    if not script.exists():
        warn("claim-ledger companion", f"script not found at {script}")
        return
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 1}),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0:
            warn("claim-ledger companion", f"exit {proc.returncode}: {proc.stderr[-200:]}")
            return
        tools_found = False
        for line in (proc.stdout or "").strip().split("\n"):
            try:
                msg = json.loads(line)
                if "result" in msg and "tools" in msg.get("result", {}):
                    tool_count = len(msg["result"]["tools"])
                    ok("claim-ledger companion", f"{tool_count} tools available")
                    tools_found = True
                    break
            except json.JSONDecodeError:
                continue
        if not tools_found:
            warn("claim-ledger companion", "no tools/list response parsed")
    except subprocess.TimeoutExpired:
        warn("claim-ledger companion", "timed out waiting for tools/list")
    except Exception as exc:
        warn("claim-ledger companion", f"error: {exc}")


def tool_surface_drift_check() -> None:
    """Generate tool-surface docs and report counts in doctor output."""
    script = Path(__file__).resolve().parent / "generate-tool-surface-docs.py"
    if not script.exists():
        warn("tool-surface docs", f"script not found at {script}")
        return
    out_path = "/tmp/doctor-tool-surface.json"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--out", out_path],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if proc.returncode != 0:
            warn("tool-surface docs", f"generation failed: {proc.stderr[-200:]}")
            return
        if not os.path.exists(out_path):
            warn("tool-surface docs", "artifact not generated")
            return
        with open(out_path) as f:
            doc = json.load(f)
        for profile_name, data in doc.get("profiles", {}).items():
            if data.get("available"):
                ok(f"tool-surface {profile_name}", f"{data['tool_count']} tools")
            else:
                warn(f"tool-surface {profile_name}", f"unavailable: {data.get('error', 'unknown')}")
        for companion_name, data in doc.get("companions", {}).items():
            if data.get("available"):
                ok(f"tool-surface {companion_name}", f"{data['tool_count']} tools")
            else:
                warn(f"tool-surface {companion_name}", f"unavailable: {data.get('error', 'unknown')}")
    except Exception as exc:
        warn("tool-surface docs", f"error: {exc}")


def write_receipt(path: str | None, host: str) -> None:
    if not path: return
    out = Path(path).expanduser()
    if out.is_dir():
        out = out / f"doctor-{host}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    payload = {"schema":"semantic-memory-agent-kit-doctor-v1","created_at":datetime.now(timezone.utc).isoformat(),"host":host,"memory_dir":str(MEMORY_DIR),"http_url":HTTP_URL,"context_governor_store":str(CG_STORE),"passed":not failed,"results":RESULTS}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"RECEIPT {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", action="store_true", help="run compact smoke; slower but proves receipt path")
    ap.add_argument("--receipt", help="write JSON doctor receipt to path or directory")
    ap.add_argument("--host", default="shared")
    args = ap.parse_args()
    print(f"Semantic Memory Agent Kit Doctor\nmemory_dir: {MEMORY_DIR}\nhttp_url:   {HTTP_URL}\ncg_store:   {CG_STORE}\n")
    sem = resolve_semantic_binary()
    if not sem: fail("semantic-memory-mcp binary", "not found; run shared/scripts/install_semantic_memory_mcp.sh or cargo install semantic-memory-mcp")
    else:
        ok("semantic-memory-mcp binary", str(sem)); MEMORY_DIR.mkdir(parents=True, exist_ok=True); ok("memory dir", str(MEMORY_DIR)); http_get("/health", "warm HTTP health"); http_get("/verify-integrity", "warm HTTP integrity", timeout=4); rpc_tools_list(sem)
    cg = resolve_cg_binary(); cg_status(cg); cg_mcp_tools_list(); config_paths(); hook_manifest_paths(args.host)
    if args.deep: compact_smoke(); claim_ledger_check(); tool_surface_drift_check()
    write_receipt(args.receipt, args.host)
    return 1 if any(r["status"] == "FAIL" for r in RESULTS) else 0

if __name__ == "__main__":
    raise SystemExit(main())
