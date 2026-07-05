from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRO_DOCTOR = ROOT / "pro" / "scripts" / "pro-doctor.py"
CLAIM_LINT = ROOT / "shared" / "scripts" / "public-claim-lint.py"


class ProDoctorAndClaimLintTests(unittest.TestCase):
    def test_public_claim_lint_blocks_unsupported_business_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "README.md"
            p.write_text("This is production-ready for enterprise customers.\n")
            proc = subprocess.run(
                [sys.executable, str(CLAIM_LINT), "--json", str(p)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertFalse(data["ok"])
            self.assertGreaterEqual(len(data["findings"]), 1)

    def test_public_claim_lint_allows_nearby_evidence_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "README.md"
            p.write_text("Evidence: receipt abc. This benchmark outperforms baseline on fixture X.\n")
            proc = subprocess.run(
                [sys.executable, str(CLAIM_LINT), "--json", str(p)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["ok"])

    def test_pro_doctor_reports_missing_config_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["RI_PRO_CONFIG"] = str(Path(td) / "missing.json")
            env.pop("RI_PRO_LICENSE_SKIP", None)
            proc = subprocess.run(
                [sys.executable, str(PRO_DOCTOR)],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertEqual(data["schema"], "RIProDoctorReceiptV1")
            self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
