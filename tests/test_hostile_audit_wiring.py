#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CURATOR_SKILLS = [
    ROOT / "hermes/skills/memory-curator/SKILL.md",
    ROOT / "claude/plugins/semantic-memory/skills/memory-curator/SKILL.md",
    ROOT / "codex/plugins/semantic-memory/skills/memory-curator/SKILL.md",
]


class TestHostileAuditWiring(unittest.TestCase):
    def test_all_curator_skills_wire_hostile_audit(self) -> None:
        for path in CURATOR_SKILLS:
            with self.subTest(path=str(path)):
                text = path.read_text(encoding="utf-8")
                self.assertIn("hostile-audit.py", text)
                self.assertIn("auditor unavailable", text)
                self.assertIn("quarantine", text.lower())
                self.assertIn("do not promote", text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
