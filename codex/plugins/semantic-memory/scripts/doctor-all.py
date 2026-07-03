#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = Path.home() / ".local/share/semantic-memory-agent-kits/receipts"
HOSTS = ["cursor", "windsurf", "cline", "roo-code", "continue", "opencode"]


def run(cmd: list[str], timeout: int = 120) -> dict:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    return {"cmd": cmd, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run all semantic-memory agent-kit doctors and write a receipt bundle.")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--deep", action="store_true", help="include context-governor compact smoke")
    args = ap.parse_args()
    out_dir = Path(args.out_dir).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    core_receipt = out_dir / f"doctor-core-{stamp}.json"
    commands = []
    core_cmd = [sys.executable, "shared/scripts/doctor_core.py", "--host", "all", "--receipt", str(core_receipt)]
    if args.deep: core_cmd.append("--deep")
    commands.append(run(core_cmd, timeout=180))
    for host in HOSTS:
        script = ROOT / host / "scripts/doctor.py"
        if script.exists():
            commands.append(run([sys.executable, str(script)], timeout=120))
    paths = [
        ROOT / "cursor/mcp.json.example", ROOT / "windsurf/mcp_config.json.example", ROOT / "cline/mcp_settings.json.example",
        ROOT / "roo-code/mcp_settings.json.example", ROOT / "continue/config.json.example", ROOT / "opencode/opencode.json.example",
        ROOT / "shared/snippets/mcp-stdio.json",
        Path.home()/"Documents/Cline/Rules/semantic-memory.md", Path.home()/".roo/rules/semantic-memory.md",
        Path.home()/".codeium/windsurf/memories/global_rules.md", Path.home()/".continue/config.yaml",
        Path.home()/".config/opencode/AGENTS.md",
    ]
    path_status = [{"path": str(p), "exists": p.exists(), "bytes": p.stat().st_size if p.exists() else None} for p in paths]
    passed = all(c["exit_code"] == 0 for c in commands)
    receipt = {"schema":"semantic-memory-agent-kit-doctor-all-v1","created_at":datetime.now(timezone.utc).isoformat(),"repo":str(ROOT),"passed":passed,"commands":commands,"path_status":path_status,"core_receipt":str(core_receipt)}
    out = out_dir / f"doctor-all-{stamp}.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"doctor-all receipt: {out}")
    print(f"passed: {passed}")
    for c in commands:
        print(f"{c['exit_code']:>3} {' '.join(c['cmd'])}")
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
