#!/usr/bin/env python3
"""Verify that a Hermes host uses only the canonical external hook directory.

This kit deliberately does not ship a duplicate hook implementation. The live
source of truth is ~/.hermes/config.yaml plus ~/.hermes/agent-hooks/.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    home = Path.home()
    parser.add_argument("--config", type=Path, default=home / ".hermes/config.yaml")
    parser.add_argument("--hook-dir", type=Path, default=home / ".hermes/agent-hooks")
    args = parser.parse_args()

    if not args.config.is_file():
        print(f"FAIL: config not found: {args.config}", file=sys.stderr)
        return 2
    if not args.hook_dir.is_dir():
        print(f"FAIL: hook directory not found: {args.hook_dir}", file=sys.stderr)
        return 2

    config = yaml.safe_load(args.config.read_text()) or {}
    hooks = config.get("hooks", {})
    if not isinstance(hooks, dict):
        print("FAIL: hooks must be a mapping", file=sys.stderr)
        return 2

    pattern = re.compile(r"python3\s+([^\s]+\.py)")
    checked = 0
    failures: list[str] = []
    expected_root = args.hook_dir.resolve()

    for event, entries in hooks.items():
        if not isinstance(entries, list):
            failures.append(f"{event}: expected a list of hook entries")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                failures.append(f"{event}: hook entry is not a mapping")
                continue
            command = str(entry.get("command", ""))
            for raw_path in pattern.findall(command):
                path = Path(raw_path).expanduser()
                if not path.is_absolute():
                    failures.append(f"{event}: hook path is not absolute: {path}")
                    continue
                try:
                    path.resolve().relative_to(expected_root)
                except ValueError:
                    failures.append(f"{event}: hook is outside {expected_root}: {path}")
                    continue
                if not path.is_file():
                    failures.append(f"{event}: hook does not exist: {path}")
                    continue
                checked += 1

    if checked == 0:
        failures.append("no Python hooks were found in config")
    if failures:
        print("FAIL: canonical hook configuration invalid", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1

    print(f"OK: {checked} configured Python hooks resolve under {expected_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
