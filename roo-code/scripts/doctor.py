#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "roo-code/mcp_settings.json.example"

def main() -> int:
    ok = True
    try:
        json.loads(EXAMPLE.read_text(encoding="utf-8"))
        print(f"OK   json: {EXAMPLE}")
    except Exception as exc:
        print(f"FAIL json: {EXAMPLE}: {exc}")
        ok = False
    proc = subprocess.run([sys.executable, str(ROOT / "shared/scripts/doctor_core.py")], text=True)
    return 0 if ok and proc.returncode == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
