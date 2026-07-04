#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = ROOT / "codex/plugins/semantic-memory/hooks"
SCRIPT = HOOK_DIR / "memory-recall.py"
spec = importlib.util.spec_from_file_location("memory_recall", SCRIPT)
assert spec and spec.loader
memory_recall = importlib.util.module_from_spec(spec)
with mock.patch("sys.path", [str(HOOK_DIR), *list(__import__("sys").path)]):
    spec.loader.exec_module(memory_recall)


class MemoryRecallOutcomeTests(unittest.TestCase):
    def test_route_outcome_good_for_strong_cosine_emission(self) -> None:
        self.assertEqual(memory_recall.route_outcome([{"cosine_similarity": 0.7}], "cosine_similarity", True), "good")

    def test_route_outcome_neutral_for_weak_emission(self) -> None:
        self.assertEqual(memory_recall.route_outcome([{"cosine_similarity": 0.59}], "cosine_similarity", True), "neutral")

    def test_record_route_outcome_posts_and_fails_open(self) -> None:
        calls: list[tuple[str, dict, float]] = []

        def fake_post(path: str, payload: dict, timeout: float = 4.0):
            calls.append((path, payload, timeout))
            return {"ok": True}

        with mock.patch.object(memory_recall, "http_post", side_effect=fake_post):
            memory_recall.record_route_outcome("when did memory change?", [{"score": 1.0}], "score", True, True)
        self.assertEqual(calls[0][0], "/record-outcome")
        self.assertEqual(calls[0][1]["outcome"], "good")

        with mock.patch.object(memory_recall, "http_post", side_effect=RuntimeError("down")):
            memory_recall.record_route_outcome("when did memory change?", [], "score", False, True)

    def test_record_route_outcome_skips_unrouted_queries(self) -> None:
        with mock.patch.object(memory_recall, "http_post") as post:
            memory_recall.record_route_outcome("simple query", [{"score": 1.0}], "score", True, False)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
