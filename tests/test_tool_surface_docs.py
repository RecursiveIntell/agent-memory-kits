#!/usr/bin/env python3
"""Tests for generate-tool-surface-docs.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "shared", "scripts", "generate-tool-surface-docs.py"
)


class TestToolSurfaceDocs(unittest.TestCase):
    def test_generates_json_artifact(self) -> None:
        """generate-tool-surface-docs.py should produce a JSON artifact with profile counts."""
        out_path = "/tmp/test-tool-surface.json"
        result = subprocess.run(
            [sys.executable, SCRIPT, "--out", out_path, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertTrue(os.path.exists(out_path))
        with open(out_path) as f:
            doc = json.load(f)
        self.assertEqual(doc["schema"], "ToolSurfaceDocV1")
        self.assertIn("profiles", doc)
        self.assertIn("lean", doc["profiles"])
        for profile_name, profile_data in doc["profiles"].items():
            self.assertIn("tool_count", profile_data)
            self.assertIn("available", profile_data)

    def test_generates_markdown(self) -> None:
        """generate-tool-surface-docs.py should produce markdown when --format markdown."""
        out_path = "/tmp/test-tool-surface-md.json"
        result = subprocess.run(
            [sys.executable, SCRIPT, "--out", out_path, "--format", "markdown"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        md_path = out_path.rsplit(".", 1)[0] + ".md"
        self.assertTrue(os.path.exists(md_path))
        with open(md_path) as f:
            content = f.read()
        self.assertIn("Tool Surface Report", content)
        self.assertIn("lean", content)

    def test_handles_missing_binary_gracefully(self) -> None:
        """Script should handle missing semantic-memory-mcp binary gracefully."""
        out_path = "/tmp/test-tool-surface-missing.json"
        result = subprocess.run(
            [sys.executable, SCRIPT, "--out", out_path,
             "--sm-binary", "/nonexistent/semantic-memory-mcp"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        with open(out_path) as f:
            doc = json.load(f)
        # Should still produce artifact, just with available=False
        for profile_name, profile_data in doc["profiles"].items():
            self.assertFalse(profile_data["available"])


if __name__ == "__main__":
    unittest.main()