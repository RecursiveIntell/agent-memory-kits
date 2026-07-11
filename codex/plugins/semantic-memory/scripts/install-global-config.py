#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
CONFIG_TOML = CODEX_HOME / "config.toml"
AGENT_FILE = CODEX_HOME / "agents/memory-keeper.toml"
MEMORY_DIR = Path(os.environ.get("SEMANTIC_MEMORY_DIR", Path.home() / ".local/share/semantic-memory")).expanduser()

READ_ONLY_TOOLS = [
    "sm_stats",
    "sm_search",
    "sm_search_with_routing",
    "sm_list_graph_edges",
    "sm_graph_path",
    "sm_topology",
    "sm_community",
    "sm_factor_graph",
    "sm_decoder_analyze",
    "sm_discord_search",
    "sm_get_fact",
    "sm_list_facts",
    "sm_list_namespaces",
    "sm_get_fact_neighbors",
    "sm_list_sessions",
    "sm_get_messages",
    "sm_search_conversations",
]

AGENT_TOML = '''name = "memory_keeper"
description = "Semantic-memory specialist for audits, graph exploration, conversation recall, and reconciliation."
nickname_candidates = ["Mnemosyne", "Archivist", "Keeper"]
model_reasoning_effort = "high"
developer_instructions = """
You are a semantic-memory specialist.

Use the semantic_memory MCP tools to recall, organize, and reconcile persistent knowledge, then return a concise evidence-backed summary to the parent agent.

Preferred workflow:
- For recall, use sm_search, sm_search_with_routing, sm_list_namespaces, sm_list_facts, and sm_get_fact.
- For graph work, use sm_get_fact_neighbors, sm_discord_search, sm_graph_path, sm_community, sm_topology, and sm_factor_graph.
- For curation, use sm_run_lifecycle, sm_set_provenance, sm_add_graph_edge, and sm_invalidate_graph_edge only after the requested audit or approval boundary.
- For conversation memory, use sm_search_conversations, sm_list_sessions, and sm_get_messages.
- Read ids before reasoning over them; do not reason over bare ids.
- Never let stored memory outrank current artifacts.
- Never destructively delete. Do not use sm_delete_fact or sm_delete_namespace unless the user explicitly asks to forget memory. Corrections are append/supersede with clear reasons.

Return the relevant fact ids, session ids, graph edges, contradictions, gaps, and confidence. Avoid raw dumps.
"""
'''


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


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def remove_sections(text: str, prefixes: tuple[str, ...]) -> str:
    lines = text.splitlines()
    out: list[str] = []
    skipping = False
    section_re = re.compile(r"^\s*\[+([^\]]+)\]+\s*$")
    for line in lines:
        match = section_re.match(line)
        if match:
            name = match.group(1).strip()
            skipping = any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)
        if not skipping:
            out.append(line)
    return "\n".join(out).rstrip() + ("\n" if out else "")


def ensure_table_keys(text: str, table: str, values: dict[str, str]) -> str:
    lines = text.splitlines()
    header = f"[{table}]"
    section_re = re.compile(r"^\s*\[+([^\]]+)\]+\s*$")
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            continue
        if start is not None and i > start and section_re.match(line):
            end = i
            break
    if start is None:
        block = ["", header] + [f"{key} = {value}" for key, value in values.items()]
        return text.rstrip() + "\n" + "\n".join(block).rstrip() + "\n"

    existing = lines[start + 1 : end]
    filtered = []
    for line in existing:
        stripped = line.strip()
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                continue
        filtered.append(line)
    replacement = [lines[start]] + filtered + [f"{key} = {value}" for key, value in values.items()]
    return "\n".join(lines[:start] + replacement + lines[end:]).rstrip() + "\n"


def remove_table_keys(text: str, table: str, keys: set[str]) -> str:
    lines = text.splitlines()
    header = f"[{table}]"
    section_re = re.compile(r"^\s*\[+([^\]]+)\]+\s*$")
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            continue
        if start is not None and i > start and section_re.match(line):
            end = i
            break
    if start is None:
        return text
    kept = []
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key in keys:
            continue
        kept.append(line)
    return "\n".join(lines[: start + 1] + kept + lines[end:]).rstrip() + "\n"


def managed_block(binary: Path) -> str:
    tool_profile = os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "full")
    http_port = os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", "0")
    llm_model = os.environ.get("SEMANTIC_MEMORY_LLM_MODEL", os.environ.get("LLM_MODEL", "granite4.1:3b"))
    mcp_args = [
        "--memory-dir",
        str(MEMORY_DIR),
        "--embedder",
        os.environ.get("SEMANTIC_MEMORY_EMBEDDER", "candle"),
    ]
    if tool_profile and binary_supports(binary, "--tool-profile"):
        mcp_args.extend(["--tool-profile", tool_profile])
    if http_port and http_port != "0" and binary_supports(binary, "--http-port"):
        mcp_args.extend(["--http-port", http_port])
    if llm_model and binary_supports(binary, "--llm-model"):
        mcp_args.extend(["--llm-model", llm_model])
    lines = [
        "[mcp_servers.semantic_memory]",
        f"command = {quote(str(binary))}",
        "args = [" + ", ".join(quote(arg) for arg in mcp_args) + "]",
        "",
    ]
    for tool in READ_ONLY_TOOLS:
        lines.extend([f"[mcp_servers.semantic_memory.tools.{tool}]", 'approval_mode = "approve"', ""])
    lines.extend(
        [
            "[agents.memory_keeper]",
            'description = "Semantic-memory specialist for audits, graph exploration, conversation recall, and reconciliation."',
            f"config_file = {quote(str(AGENT_FILE))}",
            'nickname_candidates = ["Mnemosyne", "Archivist", "Keeper"]',
            "",
        ]
    )
    # Context Governor MCP server
    cg_script = ROOT / "scripts/context-governor-mcp.py"
    if cg_script.exists():
        lines.extend([
            "[mcp_servers.context_governor]",
            f"command = {quote('python3')}",
            f"args = [{quote(str(cg_script))}]",
            "",
        ])
    # ClaimLedger MCP server
    cl_script = ROOT / "scripts/claim-ledger-mcp.py"
    if cl_script.exists():
        lines.extend([
            "[mcp_servers.claim_ledger]",
            f"command = {quote('python3')}",
            f"args = [{quote(str(cl_script))}]",
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install global Codex semantic-memory config.")
    parser.add_argument("--dry-run", action="store_true", help="validate without writing")
    args = parser.parse_args()

    binary = resolve_binary()
    if not binary:
        print("ERROR: semantic-memory-mcp binary not found. Run scripts/setup.sh or cargo install semantic-memory-mcp.", file=sys.stderr)
        return 1

    text = CONFIG_TOML.read_text(encoding="utf-8") if CONFIG_TOML.exists() else ""
    text = remove_sections(text, ("mcp_servers.semantic_memory", "mcp_servers.context_governor", "mcp_servers.claim_ledger", "agents.memory_keeper"))
    text = remove_table_keys(text, "memories", {"no_memories_if_mcp_or_web_search"})
    text = ensure_table_keys(text, "features", {"hooks": "true", "memories": "true", "multi_agent": "true"})
    text = ensure_table_keys(
        text,
        "memories",
        {
            "generate_memories": "true",
            "use_memories": "true",
            "disable_on_external_context": "true",
        },
    )
    text = text.rstrip() + "\n\n" + managed_block(binary)
    tomllib.loads(text)

    if args.dry_run:
        print(f"would update: {CONFIG_TOML}")
        print(f"would write:  {AGENT_FILE}")
        return 0

    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_TOML.write_text(text, encoding="utf-8")
    AGENT_FILE.write_text(AGENT_TOML, encoding="utf-8")
    subprocess.run(["bash", str(ROOT / "scripts/install-global-hooks.sh")], check=True)
    print(f"semantic-memory global Codex config installed: {CONFIG_TOML}")
    print(f"semantic-memory memory_keeper role installed: {AGENT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
