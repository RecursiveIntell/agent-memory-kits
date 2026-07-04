#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = ROOT / "hermes/hooks"
SCRIPT = HOOK_DIR / "sm-auto-edge.py"
spec = importlib.util.spec_from_file_location("sm_auto_edge", SCRIPT)
assert spec and spec.loader
sm_auto_edge = importlib.util.module_from_spec(spec)
with mock.patch("sys.path", [str(HOOK_DIR), *list(__import__("sys").path)]):
    spec.loader.exec_module(sm_auto_edge)


class HermesToolReceiptTests(unittest.TestCase):
    def test_post_tool_hook_writes_typed_trace_digest_receipt(self) -> None:
        payload = {"tool_name": "terminal", "tool_input": {"command": "true"}, "tool_output": {"exit_code": 0}, "session_id": "abcdef1234567890"}
        calls: list[tuple[str, dict, float]] = []

        def fake_post(path: str, body: dict, timeout: float = 4.0):
            calls.append((path, body, timeout))
            return {"ok": True}

        with mock.patch.object(sm_auto_edge, "read_payload", return_value=payload), mock.patch.object(sm_auto_edge, "http_post", side_effect=fake_post):
            self.assertEqual(sm_auto_edge.main(), 0)

        content = calls[0][1]["content"]
        self.assertIn("semantic-memory-tool-receipt-v1", content)
        self.assertIn("trace_id:tool:terminal:", content)
        self.assertIn('"algorithm":"sha256"', content)
        self.assertIn('"type":"tool_action_receipt"', content)
        self.assertIn('"exit_code":0', content)
        self.assertIn('"success":true', content)

    def test_post_tool_hook_skips_noisy_tools(self) -> None:
        payload = {"tool_name": "todo", "tool_input": {}, "tool_output": {}}
        with mock.patch.object(sm_auto_edge, "read_payload", return_value=payload), mock.patch.object(sm_auto_edge, "http_post") as post:
            self.assertEqual(sm_auto_edge.main(), 0)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
