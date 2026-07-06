#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = ROOT / "hermes/hooks"
SCRIPT = HOOK_DIR / "sm-recall.py"
spec = importlib.util.spec_from_file_location("hermes_sm_recall", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
# Isolate sys.path and clear cached `common` module so hermes/hooks/common.py
# is used, not the codex one that may have been imported by an earlier test.
# Keep stdlib paths so that `json`, `os`, etc. are still importable.
_saved_path = list(sys.path)
sys.modules.pop("common", None)
_stdlib = [p for p in sys.path if "lib" in p and "python" in p]
sys.path[:] = [str(HOOK_DIR)] + _stdlib
try:
    spec.loader.exec_module(module)
finally:
    sys.path[:] = _saved_path


class HermesRoutingTests(unittest.TestCase):
    def test_warm_search_uses_plain_search_for_class_a(self) -> None:
        calls: list[tuple[str, dict, float]] = []

        def fake_post(path: str, payload: dict, timeout: float = 4.0):
            calls.append((path, payload, timeout))
            return {"ok": True, "results": []}

        with mock.patch.object(module, "http_post", side_effect=fake_post):
            result, warm = module.warm_search("simple memory query", 8, "A")
        self.assertTrue(warm)
        self.assertEqual(result["ok"], True)
        self.assertEqual(calls[0][0], "/search")
        self.assertNotIn("query_class", calls[0][1])

    def test_warm_search_uses_server_routed_search_for_complex_class(self) -> None:
        calls: list[tuple[str, dict, float]] = []

        def fake_post(path: str, payload: dict, timeout: float = 4.0):
            calls.append((path, payload, timeout))
            return {"ok": True, "results": [], "routed": True}

        with mock.patch.object(module, "http_post", side_effect=fake_post):
            result, warm = module.warm_search("summarize all memory architecture", 8, "D", namespaces=["hermes"])
        self.assertTrue(warm)
        self.assertEqual(result["routed"], True)
        self.assertEqual(calls[0][0], "/search-routed")
        self.assertEqual(calls[0][1]["query_class"], "D")
        self.assertEqual(calls[0][1]["namespaces"], ["hermes"])

    def test_record_routing_outcome_skips_class_a_and_posts_complex(self) -> None:
        with mock.patch.object(module, "http_post") as post:
            module.record_routing_outcome("simple", "A", "good")
        post.assert_not_called()

        with mock.patch.dict(module.os.environ, {"SM_RECALL_RECORD_OUTCOME": "0"}):
            with mock.patch.object(module, "http_post") as post:
                module.record_routing_outcome("summarize memory", "D", "good")
            post.assert_not_called()

        calls: list[tuple[str, dict, float]] = []

        def fake_post(path: str, payload: dict, timeout: float = 4.0):
            calls.append((path, payload, timeout))
            return {"ok": True}

        with mock.patch.object(module, "http_post", side_effect=fake_post):
            module.record_routing_outcome("summarize memory", "D", "good")
        self.assertEqual(calls[0][0], "/record-outcome")
        self.assertEqual(calls[0][1]["query_class"], "D")
        self.assertEqual(calls[0][1]["outcome"], "good")

        with mock.patch.object(module, "http_post", side_effect=RuntimeError("down")):
            module.record_routing_outcome("summarize memory", "D", "bad")


if __name__ == "__main__":
    unittest.main()


class HermesRecallAdmissionWiringTests(unittest.TestCase):
    def test_namespace_match_uses_individual_namespace_members(self) -> None:
        script = ROOT / "hermes" / "hooks" / "sm-recall.py"
        content = script.read_text(encoding="utf-8")
        self.assertIn("namespace_tokens = {ns for group in namespace_passes(prompt, cwd) for ns in group}", content)
        self.assertIn("ns_match = bool(ns) and ns in namespace_tokens", content)

