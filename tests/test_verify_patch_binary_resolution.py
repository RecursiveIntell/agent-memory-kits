from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared" / "scripts" / "verify-patch.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_patch_module", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class VerifyPatchBinaryResolutionTests(unittest.TestCase):
    def test_auto_prefers_env_binary(self) -> None:
        mod = load_module()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "forge-pilot"
            p.write_text("#!/bin/sh\nexit 0\n")
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
            old = os.environ.get("RI_FORGE_BINARY")
            os.environ["RI_FORGE_BINARY"] = str(p)
            try:
                self.assertEqual(mod._resolve_forge_binary("auto"), p)
            finally:
                if old is None:
                    os.environ.pop("RI_FORGE_BINARY", None)
                else:
                    os.environ["RI_FORGE_BINARY"] = old

    def test_explicit_nonexistent_path_is_preserved_for_fallback_tests(self) -> None:
        mod = load_module()
        p = Path("/nonexistent/forge-engine")
        self.assertEqual(mod._resolve_forge_binary(str(p)), p)


if __name__ == "__main__":
    unittest.main()
