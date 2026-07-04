#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/doctor_core.py"
spec = importlib.util.spec_from_file_location("doctor_core", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DoctorTruthFloorTests(unittest.TestCase):
    def setUp(self) -> None:
        module.RESULTS.clear()

    def test_hook_manifest_paths_fails_missing_hook_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hermes = root / "hermes"
            hermes.mkdir()
            (hermes / "plugin.json").write_text(
                json.dumps({"hermes": {"hooks": {"pre_llm_call": "hooks/missing.py"}}}),
                encoding="utf-8",
            )
            with mock.patch.object(module, "ROOT", root):
                module.hook_manifest_paths("hermes")
            self.assertTrue(any(row["status"] == "FAIL" and "missing.py" in row["detail"] for row in module.RESULTS))

    def test_hook_manifest_paths_accepts_executable_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hermes = root / "hermes"
            hook_dir = hermes / "hooks"
            hook_dir.mkdir(parents=True)
            hook = hook_dir / "ok.py"
            hook.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            hook.chmod(0o755)
            (hermes / "plugin.json").write_text(
                json.dumps({"hermes": {"hooks": {"pre_llm_call": "hooks/ok.py"}}}),
                encoding="utf-8",
            )
            with mock.patch.object(module, "ROOT", root):
                module.hook_manifest_paths("hermes")
            self.assertTrue(any(row["status"] == "OK" and "1 hook" in row["detail"] for row in module.RESULTS))


if __name__ == "__main__":
    unittest.main()
