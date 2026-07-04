#!/usr/bin/env python3
"""Tests for agent-guard-mcp.py."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "shared", "scripts", "agent-guard-mcp.py")


class TestAgentGuardMcp(unittest.TestCase):
    def test_lists_tools(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT, "--list-tools"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        tools = json.loads(result.stdout)
        names = [t["name"] for t in tools]
        self.assertIn("agent_guard_security_posture", names)
        self.assertIn("agent_guard_check_process", names)

    def test_tool_descriptions_are_admin_only(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT, "--list-tools"],
            capture_output=True, text=True, timeout=10,
        )
        tools = json.loads(result.stdout)
        for tool in tools:
            self.assertIn("ADMIN", tool["description"].upper())

    def test_security_posture_returns_mechanisms(self) -> None:
        spec = importlib.util.spec_from_file_location("agm", SCRIPT)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.handle_tool_call("agent_guard_security_posture", {})
        self.assertEqual(result["schema"], "SecurityPostureV1")
        self.assertIn("available_mechanisms", result)
        mechanisms = result["available_mechanisms"]
        self.assertIn("cgroup_v2", mechanisms)
        self.assertIn("seccomp", mechanisms)
        self.assertIn("landlock", mechanisms)
        self.assertIn("bpf_lsm", mechanisms)

    def test_check_process_returns_info(self) -> None:
        spec = importlib.util.spec_from_file_location("agm", SCRIPT)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.handle_tool_call("agent_guard_check_process", {"pid": 1})
        self.assertEqual(result["schema"], "ProcessCheckV1")
        self.assertEqual(result["pid"], 1)
        self.assertIn("cgroup", result)
        self.assertIn("seccomp", result)


if __name__ == "__main__":
    unittest.main()