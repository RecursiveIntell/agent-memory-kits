#!/usr/bin/env python3
"""Claude Stop capture nudges continue once, then let the turn end."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "claude/plugins/semantic-memory/hooks/memory-capture-nudge.sh"


def _run(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
        cwd=str(ROOT),
        env={**os.environ},
    )


class CaptureNudgeStopTests(unittest.TestCase):
    def test_first_stop_nudges(self) -> None:
        proc = _run({"hook_event_name": "Stop", "stop_hook_active": False})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "Stop")
        self.assertIn("sm_add_fact", ctx)

    def test_repeated_stop_callback_emits_no_stdout(self) -> None:
        proc = _run({"hookEventName": "Stop", "stop_hook_active": True})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_precompact_still_nudges(self) -> None:
        proc = _run({"hookEventName": "PreCompact", "trigger": "auto"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PreCompact")
        self.assertIn("sm_add_fact", ctx)
        self.assertIn("compacted", ctx.lower())

    def test_hooks_json_registers_stop(self) -> None:
        hooks = json.loads((ROOT / "claude/plugins/semantic-memory/hooks/hooks.json").read_text())
        self.assertIn("Stop", hooks.get("hooks", {}))
        self.assertIn("PreCompact", hooks.get("hooks", {}))


if __name__ == "__main__":
    unittest.main()
