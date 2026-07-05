#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "scripts"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))
SCRIPT = SHARED / "tool_receipts.py"
spec = importlib.util.spec_from_file_location("tool_receipts", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ToolReceiptSpineTests(unittest.TestCase):
    def test_canonical_tool_receipt_contains_trace_ctx_and_digest(self) -> None:
        receipt = module.build_tool_receipt(
            tool="terminal",
            summary="terminal: true",
            tool_input={"command": "true"},
            tool_output={"exit_code": 0},
            cwd="/tmp/work",
            session_id="abcdef1234567890",
            scope="tool",
        )

        self.assertEqual(receipt["schema"], "llm-tool-runtime-compatible-tool-receipt-v1")
        self.assertEqual(receipt["type"], "tool_action_receipt")
        self.assertEqual(receipt["tool"], "terminal")
        self.assertEqual(receipt["trace_ctx"]["scope"], "tool")
        self.assertTrue(receipt["trace_ctx"]["trace_id"].startswith("trace:tool:"))
        self.assertEqual(receipt["digest"]["algorithm"], "sha256")
        self.assertEqual(receipt["status"]["exit_code"], 0)
        self.assertEqual(receipt["status"]["success"], True)
        self.assertEqual(receipt["session_id"], "abcdef123456")

    def test_receipt_content_uses_canonical_schema_and_trace(self) -> None:
        receipt = module.build_tool_receipt(
            tool="patch",
            summary="patch: src/lib.rs",
            tool_input={"path": "src/lib.rs"},
            tool_output={"success": True},
        )

        content = module.tool_receipt_content(receipt)

        self.assertIn("llm-tool-runtime-compatible-tool-receipt-v1", content)
        self.assertIn("trace_id:trace:tool:", content)
        self.assertIn("sha256:", content)
        self.assertIn("patch: src/lib.rs", content)


if __name__ == "__main__":
    unittest.main()
