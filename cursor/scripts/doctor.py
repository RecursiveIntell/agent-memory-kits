#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check_json(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL json: {path}: {exc}")
        return False
    print(f"OK   json: {path}")
    return True


def main() -> int:
    ok = check_json(ROOT / "cursor/mcp.json.example")
    proc = subprocess.run([sys.executable, str(ROOT / "shared/scripts/doctor_core.py")], text=True)
    return 0 if ok and proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
