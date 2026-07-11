#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = ROOT / "hermes/hooks"
SCRIPT = HOOK_DIR / "sm-primer.py"
spec = importlib.util.spec_from_file_location("hermes_sm_primer", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
_saved_path = list(sys.path)
sys.modules.pop("common", None)
_stdlib = [p for p in sys.path if "lib" in p and "python" in p]
sys.path[:] = [str(HOOK_DIR)] + _stdlib
try:
    spec.loader.exec_module(module)
finally:
    sys.path[:] = _saved_path


class HermesWitnessedPrimerTests(unittest.TestCase):
    def test_project_recall_uses_witnessed_rpc_not_http_search(self) -> None:
        calls: list[tuple[str, dict]] = []

        def fake_rpc(tool: str, arguments: dict, timeout: int = 8):
            calls.append((tool, arguments))
            if tool == "sm_stats":
                return {"ok": True, "facts": 1, "documents": 0, "chunks": 0, "graph_edges": 0}
            return {"ok": True, "receipt_id": "receipt-1", "state_view": {"kind": "Current"}, "results": []}

        with mock.patch.object(module, "read_payload", return_value={"cwd": str(ROOT)}), \
             mock.patch.object(module, "project_name", return_value=("agent-memory-kits", True)), \
             mock.patch.object(module, "http_post", return_value=None), \
             mock.patch.object(module, "http_get", return_value=None), \
             mock.patch.object(module, "rpc_call", side_effect=fake_rpc), \
             mock.patch.object(module, "emit_context"):
            self.assertEqual(module.main(), 0)

        self.assertIn(("sm_search_witnessed", {"query": "agent-memory-kits codebase project overview", "top_k": 5}), calls)
        self.assertNotIn(("sm_search", {"query": "agent-memory-kits codebase project overview", "top_k": 5}), calls)


if __name__ == "__main__":
    unittest.main()
