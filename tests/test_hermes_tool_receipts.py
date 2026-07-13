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
    def test_plugin_does_not_register_post_tool_hook_before_trusted_admission_exists(self) -> None:
        manifest = __import__("json").loads((ROOT / "hermes/plugin.json").read_text())
        hooks = manifest["hermes"]["hooks"]
        self.assertNotIn("post_tool_call", hooks)
        self.assertNotIn("post_tool_use", hooks)

    def test_hermes_runtime_defaults_do_not_target_legacy_semantic_store(self) -> None:
        active = [
            ROOT / "hermes/tools.py",
            ROOT / "hermes/hooks/common.py",
            ROOT / "hermes/hooks/sm-recall.py",
            ROOT / "hermes/scripts/ingest_codebase.py",
        ]
        for path in active:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(".local/share/semantic-memory", text, str(path))
            self.assertIn(".hermes/semantic-memory.db", text, str(path))

    def test_post_tool_hook_writes_typed_trace_digest_receipt(self) -> None:
        payload = {"tool_name": "terminal", "tool_input": {"command": "true"}, "tool_output": {"exit_code": 0}, "session_id": "abcdef1234567890"}
        calls: list[tuple[str, dict, float]] = []

        def fake_post(path: str, body: dict, timeout: float = 4.0):
            calls.append((path, body, timeout))
            return {"ok": True}

        with mock.patch.object(sm_auto_edge, "read_payload", return_value=payload), mock.patch.object(sm_auto_edge, "http_post", side_effect=fake_post):
            self.assertEqual(sm_auto_edge.main(), 0)

        path, body, _timeout = calls[0]
        self.assertEqual(path, "/add-tool-receipt")
        self.assertEqual(body["namespace"], "tool-receipts")
        self.assertEqual(body["source"], "hermes-post-tool-call-hook")
        receipt = body["receipt"]
        self.assertEqual(receipt["schema"], "llm-tool-runtime-compatible-tool-receipt-v1")
        self.assertTrue(receipt["trace_ctx"]["trace_id"].startswith("trace:tool:"))
        self.assertEqual(receipt["digest"]["algorithm"], "sha256")
        self.assertEqual(receipt["type"], "tool_action_receipt")
        self.assertEqual(receipt["status"]["exit_code"], 0)
        self.assertTrue(receipt["status"]["success"])

    def test_tool_receipt_trace_is_stable_and_binds_host_lineage(self) -> None:
        payload = {
            "tool_name": "terminal",
            "tool_input": {"command": "true"},
            "tool_output": {"exit_code": 0},
            "session_id": "session-1",
            "task_id": "task-1",
            "tool_call_id": "call-1",
            "api_request_id": "request-1",
        }

        def capture(current: dict) -> str:
            calls = []
            with mock.patch.object(sm_auto_edge, "read_payload", return_value=current), mock.patch.object(
                sm_auto_edge, "http_post", side_effect=lambda path, body, timeout=4.0: calls.append(body) or {"ok": True}
            ):
                self.assertEqual(sm_auto_edge.main(), 0)
            receipt = calls[0]["receipt"]
            self.assertEqual(receipt["host_lineage"]["task_id"], "task-1")
            self.assertEqual(receipt["host_lineage"]["api_request_id"], "request-1")
            return receipt["trace_ctx"]["trace_id"]

        first = capture(payload)
        second = capture(dict(payload))
        changed = capture({**payload, "tool_call_id": "call-2"})
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        self.assertTrue(first.startswith("trace:tool:"))

    def test_post_tool_hook_skips_noisy_tools(self) -> None:
        payload = {"tool_name": "todo", "tool_input": {}, "tool_output": {}}
        with mock.patch.object(sm_auto_edge, "read_payload", return_value=payload), mock.patch.object(sm_auto_edge, "http_post") as post:
            self.assertEqual(sm_auto_edge.main(), 0)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
