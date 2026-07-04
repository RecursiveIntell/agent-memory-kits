#!/usr/bin/env python3
"""Tests for trace_ids.py."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared", "scripts"))
from trace_ids import generate_trace_id, generate_content_digest, TraceCtx


class TestTraceIds(unittest.TestCase):
    def test_trace_id_format(self) -> None:
        """Trace ID should have trace: prefix and be unique."""
        tid1 = generate_trace_id("release-gate")
        tid2 = generate_trace_id("release-gate")
        self.assertTrue(tid1.startswith("trace:release-gate:"))
        self.assertNotEqual(tid1, tid2)

    def test_content_digest_stable(self) -> None:
        """Same content should produce same digest."""
        d1 = generate_content_digest("hello world")
        d2 = generate_content_digest("hello world")
        d3 = generate_content_digest("hello world!")
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, d3)
        self.assertTrue(d1.startswith("sha256:"))

    def test_trace_ctx_serializable(self) -> None:
        """TraceCtx should be JSON serializable via to_dict."""
        ctx = TraceCtx(scope="audit", trace_id="trace:audit:abc123")
        d = ctx.to_dict()
        self.assertIn("scope", d)
        self.assertIn("trace_id", d)
        self.assertIn("timestamp", d)
        self.assertNotIn("parent_trace_id", d)  # None should be removed
        ctx2 = TraceCtx.from_dict(d)
        self.assertEqual(ctx2.trace_id, ctx.trace_id)
        self.assertEqual(ctx2.scope, ctx.scope)

    def test_trace_ctx_with_parent(self) -> None:
        """TraceCtx with parent_trace_id should serialize it."""
        ctx = TraceCtx(
            scope="subtask",
            trace_id="trace:subtask:def456",
            parent_trace_id="trace:parent:abc123",
        )
        d = ctx.to_dict()
        self.assertIn("parent_trace_id", d)
        self.assertEqual(d["parent_trace_id"], "trace:parent:abc123")

    def test_trace_ctx_create(self) -> None:
        """TraceCtx.create should generate a fresh trace ID."""
        ctx = TraceCtx.create("test-scope")
        self.assertTrue(ctx.trace_id.startswith("trace:test-scope:"))
        self.assertEqual(ctx.scope, "test-scope")
        self.assertTrue(ctx.timestamp)


if __name__ == "__main__":
    unittest.main()