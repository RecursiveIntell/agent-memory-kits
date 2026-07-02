#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CONFIG = {
    "cursor": {"label":"Cursor", "project_mcp": ".cursor/mcp.json", "user_mcp": None},
    "windsurf": {"label":"Windsurf", "project_mcp": ".windsurf/mcp_config.json", "user_mcp": None},
    "cline": {"label":"Cline", "project_mcp": ".cline/mcp_settings.json", "user_mcp": None},
    "roo-code": {"label":"Roo Code", "project_mcp": ".roo/mcp_settings.json", "user_mcp": None},
    "continue": {"label":"Continue", "project_mcp": ".continue/config.json", "user_mcp": None},
    "opencode": {"label":"OpenCode", "project_mcp": ".opencode/opencode.json", "user_mcp": ".config/opencode/opencode.json"},
}


def run(cmd: list[str], dry: bool = False) -> str:
    if dry:
        print("DRY", " ".join(cmd)); return ""
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or f"command failed: {' '.join(cmd)}")
    if proc.stdout.strip(): print(proc.stdout.strip())
    return proc.stdout.strip()


def mcp_config(host: str) -> dict:
    runner = ROOT / host / "scripts/run-server.sh"
    return {
        "mcpServers": {
            "semantic-memory": {
                "command": str(runner),
                "env": {
                    "SEMANTIC_MEMORY_DIR": os.environ.get("SEMANTIC_MEMORY_DIR", "${HOME}/.local/share/semantic-memory"),
                    "SEMANTIC_MEMORY_TOOL_PROFILE": os.environ.get("SEMANTIC_MEMORY_TOOL_PROFILE", "lean"),
                    "SEMANTIC_MEMORY_HTTP_PORT": os.environ.get("SEMANTIC_MEMORY_HTTP_PORT", "1739"),
                },
            },
            "context-governor": {
                "command": str(ROOT / "shared/scripts/context-governor-mcp.py"),
                "env": {"CONTEXT_GOVERNOR_STORE": os.environ.get("CONTEXT_GOVERNOR_STORE", "${HOME}/.local/share/context-governor/receipts")},
            },
        }
    }


def backup(path: Path, dry: bool) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        i = 1
        while bak.exists():
            bak = path.with_suffix(path.suffix + f".bak{i}"); i += 1
        if dry: print(f"DRY backup {path} -> {bak}")
        else: path.rename(bak); print(f"backup: {bak}")


def write_json(path: Path, data: dict, dry: bool) -> None:
    if dry:
        print(f"DRY write {path}\n{json.dumps(data, indent=2)}"); return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path, dry)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote MCP config: {path}")


def print_snippet(host: str) -> None:
    cfg = HOST_CONFIG[host]
    print(f"{cfg['label']} MCP config snippet:")
    print(json.dumps(mcp_config(host), indent=2))
    print()
    print("Verify:")
    print(f"  {host}/scripts/doctor.py")
    print("  shared/scripts/doctor-all.py --deep")


def install_binaries(dry: bool) -> None:
    if dry:
        print("DRY install semantic-memory-mcp/context-governor")
        return
    print("semantic-memory-mcp:", run([str(ROOT / "shared/scripts/install_semantic_memory_mcp.sh")]))
    try:
        print("context-governor:", run([str(ROOT / "shared/scripts/install_context_governor.sh")]))
    except SystemExit as exc:
        print(f"WARN context-governor install skipped: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Setup a semantic-memory/context-governor agent kit.")
    ap.add_argument("host", choices=sorted(HOST_CONFIG))
    ap.add_argument("--write-project", nargs="?", const=".", help="write project-local rule/config files; optional project path")
    ap.add_argument("--write-user", action="store_true", help="write safe user/global rule files; MCP config only where known safe")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    host=args.host; cfg=HOST_CONFIG[host]
    install_binaries(args.dry_run)
    print_snippet(host)
    if args.write_project is not None:
        workspace=Path(args.write_project).expanduser().resolve()
        run([str(ROOT/"shared/scripts/install-context-rules.py"), host, "--scope", "workspace", "--workspace", str(workspace)], dry=args.dry_run)
        write_json(workspace / cfg["project_mcp"], mcp_config(host), args.dry_run)
    if args.write_user:
        if host == "cursor":
            print("WARN Cursor global User Rules are UI-managed; use --write-project for .cursor/rules/*.mdc.")
        else:
            run([str(ROOT/"shared/scripts/install-context-rules.py"), host, "--scope", "global"], dry=args.dry_run)
        if cfg.get("user_mcp"):
            write_json(Path.home()/cfg["user_mcp"], mcp_config(host), args.dry_run)
        else:
            print(f"MCP user config path for {cfg['label']} is not auto-written; copy snippet per host docs.")
    if args.write_project is None and not args.write_user:
        print(f"Project install: {host}/scripts/setup.sh --write-project /path/to/project")
        print(f"User/global rules: {host}/scripts/setup.sh --write-user")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
