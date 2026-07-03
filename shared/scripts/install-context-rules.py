#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE = (ROOT / "shared/rules/semantic-memory-context.md").read_text(encoding="utf-8")
CG_RULE = (ROOT / "shared/rules/context-governor.md").read_text(encoding="utf-8")
CL_RULE = (ROOT / "shared/rules/claim-ledger.md").read_text(encoding="utf-8")
RG_RULE = (ROOT / "shared/rules/release-gate.md").read_text(encoding="utf-8")
CONTEXT = ROOT / "shared/scripts/semantic-memory-context.py"
CG_COMPACT = ROOT / "shared/scripts/context-governor-compact.py"
START = "<!-- semantic-memory-context:start -->"
END = "<!-- semantic-memory-context:end -->"


def material() -> str:
    sm = RULE.replace("/ABSOLUTE/PATH/TO/semantic-memory-agent-kits/shared/scripts/semantic-memory-context.py", str(CONTEXT))
    cg = CG_RULE.replace("/ABSOLUTE/PATH/TO/semantic-memory-agent-kits/shared/scripts/context-governor-compact.py", str(CG_COMPACT))
    return sm.rstrip() + "\n\n---\n\n" + cg.rstrip() + "\n\n---\n\n" + CL_RULE.rstrip() + "\n\n---\n\n" + RG_RULE.rstrip() + "\n"


def managed_write(path: Path, content: str, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    block = f"{START}\n{content.rstrip()}\n{END}\n"
    if append and path.exists():
        old = path.read_text(encoding="utf-8")
        if START in old and END in old:
            before = old.split(START, 1)[0]
            after = old.split(END, 1)[1]
            path.write_text(before.rstrip() + "\n\n" + block + after.lstrip(), encoding="utf-8")
        else:
            path.write_text(old.rstrip() + "\n\n" + block, encoding="utf-8")
    else:
        path.write_text(block, encoding="utf-8")
    print(f"installed context rule: {path}")


def install(host: str, scope: str, workspace: Path) -> None:
    home = Path.home()
    text = material()
    if host == "cline":
        if scope == "global":
            managed_write(home / "Documents/Cline/Rules/semantic-memory.md", text)
        else:
            managed_write(workspace / ".clinerules/semantic-memory.md", text)
    elif host == "roo-code":
        if scope == "global":
            managed_write(home / ".roo/rules/semantic-memory.md", text)
        else:
            managed_write(workspace / ".roo/rules/semantic-memory.md", text)
    elif host == "windsurf":
        if scope == "global":
            managed_write(home / ".codeium/windsurf/memories/global_rules.md", text, append=True)
        else:
            managed_write(workspace / ".devin/rules/semantic-memory.md", text)
    elif host == "cursor":
        # Cursor project rules use .mdc. Global User Rules are UI-managed, so project scope is the reliable file path.
        if scope == "global":
            raise SystemExit("Cursor global User Rules are UI-managed; install a workspace rule with --scope workspace.")
        body = "---\ndescription: Use semantic-memory persistent recall before non-trivial agent work\nalwaysApply: true\n---\n\n" + text
        managed_write(workspace / ".cursor/rules/semantic-memory.mdc", body)
    elif host == "continue":
        # Continue supports `rules: - uses: file://...` in config.yaml. Install the file and, for a missing config,
        # create the minimum v1 config. If a config already exists, print the stanza instead of risking a bad YAML merge.
        path = home / ".continue/rules/semantic-memory.md" if scope == "global" else workspace / ".continue/rules/semantic-memory.md"
        managed_write(path, text)
        cfg = (home / ".continue/config.yaml") if scope == "global" else (workspace / ".continue/config.yaml")
        if not cfg.exists():
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                "name: semantic-memory-context\n"
                "version: 1.0.0\n"
                "schema: v1\n"
                "rules:\n"
                f"  - uses: file://{path}\n",
                encoding="utf-8",
            )
            print(f"installed Continue config: {cfg}")
        else:
            print("Continue config already exists; add this rule if not already present:")
            print("rules:")
            print(f"  - uses: file://{path}")
    elif host == "opencode":
        base = home / ".config/opencode" if scope == "global" else workspace / ".opencode"
        managed_write(base / "AGENTS.md", text, append=True)
        cmd = """---\ndescription: Retrieve semantic-memory context for a task before acting\n---\n\nRun this command with the user's task/prompt as stdin or argument, then use the returned recall as non-authoritative context:\n\n```bash\n{ctx} --prompt \"$ARGUMENTS\"\n```\n""".format(ctx=CONTEXT)
        managed_write(base / "commands/semantic-memory-recall.md", cmd)
    else:
        raise SystemExit(f"unknown host: {host}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("host", choices=["cursor", "windsurf", "cline", "roo-code", "continue", "opencode"])
    ap.add_argument("--scope", choices=["global", "workspace"], default="workspace")
    ap.add_argument("--workspace", default=os.getcwd())
    args = ap.parse_args()
    install(args.host, args.scope, Path(args.workspace).resolve())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
