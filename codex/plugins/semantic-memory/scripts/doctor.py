#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
CONFIG_TOML = CODEX_HOME / "config.toml"
HOOKS_JSON = CODEX_HOME / "hooks.json"
MEMORY_KEEPER_ROLE = CODEX_HOME / "agents/memory-keeper.toml"
MARKETPLACE = Path.home() / ".agents/plugins/marketplace.json"
MEMORY_DIR = Path(os.environ.get("SEMANTIC_MEMORY_DIR", Path.home() / ".local/share/semantic-memory")).expanduser()
READ_ONLY_TOOLS = {
    "sm_community",
    "sm_decoder_analyze",
    "sm_discord_search",
    "sm_factor_graph",
    "sm_get_fact",
    "sm_get_fact_neighbors",
    "sm_get_messages",
    "sm_graph_path",
    "sm_list_facts",
    "sm_list_graph_edges",
    "sm_list_namespaces",
    "sm_list_sessions",
    "sm_search",
    "sm_search_conversations",
    "sm_search_with_routing",
    "sm_stats",
    "sm_topology",
}
EXPECTED_TOOLS = READ_ONLY_TOOLS | {
    "sm_add_fact",
    "sm_add_graph_edge",
    "sm_add_message",
    "sm_create_session",
    "sm_delete_fact",
    "sm_delete_namespace",
    "sm_ingest_document",
    "sm_invalidate_graph_edge",
    "sm_run_lifecycle",
    "sm_set_provenance",
    "sm_supersede_fact",
}
LEAN_REQUIRED_TOOLS = {
    "sm_add_fact",
    "sm_add_graph_edge",
    "sm_delete_fact",
    "sm_delete_namespace",
    "sm_discord_search",
    "sm_get_fact",
    "sm_get_fact_neighbors",
    "sm_get_messages",
    "sm_graph_path",
    "sm_ingest_document",
    "sm_list_facts",
    "sm_list_graph_edges",
    "sm_list_namespaces",
    "sm_search",
    "sm_search_conversations",
    "sm_search_with_routing",
    "sm_set_provenance",
    "sm_stats",
    "sm_supersede_fact",
}


def ok(label: str, detail: str = "") -> None:
    print(f"OK   {label}{': ' + detail if detail else ''}")


def warn(label: str, detail: str = "") -> None:
    print(f"WARN {label}{': ' + detail if detail else ''}")


def fail(label: str, detail: str = "") -> None:
    print(f"FAIL {label}{': ' + detail if detail else ''}")


def resolve_binary() -> Path | None:
    env = os.environ.get("SEMANTIC_MEMORY_MCP_BIN")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser())
    candidates.extend(
        [
            Path.home() / "Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp",
            Path.home() / ".local/bin/semantic-memory-mcp",
        ]
    )
    which = shutil.which("semantic-memory-mcp")
    if which:
        candidates.append(Path(which))
    candidates.append(Path.home() / ".cargo/bin/semantic-memory-mcp")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def binary_help(binary: Path) -> str:
    try:
        proc = subprocess.run(
            [str(binary), "--help"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return ""
    return f"{proc.stdout}\n{proc.stderr}"


def binary_supports(binary: Path, flag: str) -> bool:
    return flag in binary_help(binary)


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def check_plugin_source() -> None:
    manifest = load_json(ROOT / ".codex-plugin/plugin.json")
    if not manifest:
        fail("plugin manifest", f"missing or invalid: {ROOT / '.codex-plugin/plugin.json'}")
        return
    if manifest.get("name") == "semantic-memory":
        ok("plugin manifest", manifest.get("version", "unknown version"))
    else:
        fail("plugin manifest", "name is not semantic-memory")
    for rel in ("skills", "mcpServers"):
        path = manifest.get(rel)
        if path:
            target = ROOT / str(path).removeprefix("./")
            if target.exists():
                ok(f"manifest {rel}", str(target))
            else:
                fail(f"manifest {rel}", str(target))


def check_marketplace() -> None:
    data = load_json(MARKETPLACE)
    if not data:
        warn("marketplace", f"missing or invalid: {MARKETPLACE}")
        return
    for entry in data.get("plugins", []):
        if entry.get("name") == "semantic-memory":
            source = entry.get("source", {})
            if source.get("source") == "local":
                base = Path.home() if MARKETPLACE == Path.home() / ".agents/plugins/marketplace.json" else MARKETPLACE.parent
                resolved = (base / source.get("path", "")).resolve()
                ok("marketplace entry", str(resolved))
            else:
                warn("marketplace entry", "semantic-memory is not a local source")
            return
    warn("marketplace entry", "semantic-memory not found")


def check_config() -> None:
    if not CONFIG_TOML.exists():
        warn("config.toml", f"missing: {CONFIG_TOML}")
        return
    text = CONFIG_TOML.read_text(encoding="utf-8", errors="replace")
    if "[mcp_servers.semantic_memory]" in text:
        ok("MCP config", "semantic_memory server configured")
    else:
        fail("MCP config", "missing [mcp_servers.semantic_memory]")
    if "[features]" in text and "hooks = true" in text:
        ok("hooks feature", "enabled")
    else:
        warn("hooks feature", "set [features].hooks = true")
    if "[memories]" in text and "no_memories_if_mcp_or_web_search = true" in text:
        ok("Codex memories coordination", "polluted MCP/search threads are excluded")
    elif "[memories]" in text and "disable_on_external_context = true" in text:
        ok("Codex memories coordination", "external-context threads are excluded")
    else:
        warn("Codex memories coordination", "run scripts/install-global-config.py")
    if "[agents.memory_keeper]" in text and MEMORY_KEEPER_ROLE.exists():
        ok("memory_keeper role", str(MEMORY_KEEPER_ROLE))
    else:
        warn("memory_keeper role", "add [agents.memory_keeper] and ~/.codex/agents/memory-keeper.toml for Codex subagent parity")
    missing = [
        tool
        for tool in sorted(READ_ONLY_TOOLS)
        if f"[mcp_servers.semantic_memory.tools.{tool}]" not in text
        or 'approval_mode = "approve"' not in text.split(f"[mcp_servers.semantic_memory.tools.{tool}]", 1)[1].split("[", 1)[0]
    ]
    if missing:
        warn("read-only MCP approvals", ", ".join(missing))
    else:
        ok("read-only MCP approvals", "approved")


def check_hooks() -> None:
    data = load_json(HOOKS_JSON)
    if not data:
        warn("global hooks", f"missing or invalid: {HOOKS_JSON}")
        return
    hooks = data.get("hooks", {})
    expected = [
        ("SessionStart", "memory-primer.py"),
        ("UserPromptSubmit", "memory-recall.py"),
        ("PreCompact", "memory-capture-nudge.py"),
        ("Stop", "memory-capture-nudge.py"),
    ]
    for event, script in expected:
        found = False
        for group in hooks.get(event, []):
            for hook in group.get("hooks", []):
                if script in hook.get("command", ""):
                    found = True
        if found:
            ok(f"{event} hook", script)
        else:
            warn(f"{event} hook", f"missing {script}; run scripts/install-global-hooks.sh")
    for script in ("codebase-auto-ingest.py",):
        found = False
        for group in hooks.get("UserPromptSubmit", []):
            for hook in group.get("hooks", []):
                if script in hook.get("command", ""):
                    found = True
        if found:
            ok("UserPromptSubmit hook", script)
        else:
            warn("UserPromptSubmit hook", f"missing {script}; run scripts/install-global-hooks.sh")
    bundled = ROOT / "hooks/hooks.json"
    if bundled.exists():
        ok("plugin-bundled hooks", str(bundled))
    else:
        warn("plugin-bundled hooks", "missing hooks/hooks.json")


def rpc_call(binary: Path, method: str, params: dict | None = None, timeout: int = 20) -> dict | None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    reqs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "semantic-memory-doctor", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}},
    ]
    stdin = "\n".join(json.dumps(item) for item in reqs) + "\n"
    cmd = [
        str(binary),
        "--memory-dir",
        str(MEMORY_DIR),
        "--embedder",
        os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle"),
    ]
    if binary_supports(binary, "--tool-profile"):
        cmd.extend(["--tool-profile", os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")])
    try:
        proc = subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=20, check=False)
    except Exception as exc:
        fail("MCP smoke", str(exc))
        return False
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") != 2:
            continue
        try:
            return msg
        except Exception:
            return None
    if proc.stderr.strip():
        return {"error": proc.stderr.strip()[-500:]}
    return None


def rpc_stats(binary: Path) -> bool:
    msg = rpc_call(binary, "tools/call", {"name": "sm_stats", "arguments": {}})
    if not msg:
        fail("MCP smoke", "no sm_stats response")
        return False
    try:
        payload = json.loads(msg["result"]["content"][0]["text"])
    except Exception:
        fail("MCP smoke", "invalid sm_stats response")
        return False
    if payload.get("ok"):
        ok(
            "MCP smoke",
            f"{payload.get('facts', 0)} facts, {payload.get('documents', 0)} docs, {payload.get('graph_edges', 0)} graph edges",
        )
        return True
    fail("MCP smoke", str(payload)[:500])
    return False


def check_tool_surface(binary: Path) -> None:
    msg = rpc_call(binary, "tools/list", {})
    tools = {tool.get("name") for tool in (msg or {}).get("result", {}).get("tools", [])}
    profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean")
    required = EXPECTED_TOOLS if profile in {"standard", "full"} else LEAN_REQUIRED_TOOLS
    missing = sorted(required - tools)
    if missing:
        fail("MCP tools", "missing " + ", ".join(missing))
    else:
        ok("MCP tools", f"{len(tools)} exposed with {profile} profile; direct-read, supersession, and recall tools present")


def check_cleanliness() -> None:
    pycache = list(ROOT.rglob("__pycache__"))
    if pycache:
        warn("__pycache__", ", ".join(str(path) for path in pycache))
    else:
        ok("__pycache__", "none")


def main() -> int:
    print(f"Semantic Memory Doctor\nplugin: {ROOT}\ncodex_home: {CODEX_HOME}\nmemory_dir: {MEMORY_DIR}\n")
    check_plugin_source()
    check_marketplace()
    check_config()
    check_hooks()
    binary = resolve_binary()
    if binary:
        ok("semantic-memory-mcp binary", str(binary))
        check_tool_surface(binary)
        rpc_stats(binary)
    else:
        fail("semantic-memory-mcp binary", "not found; run scripts/setup.sh")
    check_cleanliness()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
