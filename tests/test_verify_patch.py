#!/usr/bin/env python3
"""Tests for verify-patch.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared" / "scripts" / "verify-patch.py"
sys.path.insert(0, str(ROOT / "shared" / "scripts"))


class VerifyPatchTests(unittest.TestCase):
    def _make_repo(self, base: Path) -> Path:
        """Create a minimal temp repo with Cargo.toml and src/lib.rs."""
        repo = base / "repo"
        (repo / "src").mkdir(parents=True, exist_ok=True)
        (repo / "Cargo.toml").write_text(
            '[package]\nname = "test-patch"\nversion = "0.1.0"\nedition = "2021"\n',
            encoding="utf-8",
        )
        (repo / "src" / "lib.rs").write_text(
            "pub fn add(a: i32, b: i32) -> i32 { a + b }\n",
            encoding="utf-8",
        )
        # init a git repo so git rev-parse HEAD works
        subprocess.run(
            ["git", "init"], cwd=str(repo), capture_output=True, timeout=10
        )
        subprocess.run(
            ["git", "add", "."], cwd=str(repo), capture_output=True, timeout=10
        )
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=str(repo),
            capture_output=True,
            timeout=10,
            env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
                 "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com"},
        )
        return repo

    def _run_verify(self, repo: Path, out_dir: Path, check_cmd: str,
                    binary_path: str | None = None) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--repo", str(repo),
            "--claim", "patch compiles and tests pass",
            "--check-cmd", check_cmd,
            "--out-dir", str(out_dir),
            "--no-memory",
        ]
        if binary_path is not None:
            cmd += ["--binary-path", binary_path]
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )

    def test_emits_verification_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = self._make_repo(base)
            out_dir = base / "receipts"
            result = self._run_verify(repo, out_dir, "true")

            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            summary = json.loads(result.stdout)
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["disposition"], "promote")

            receipt_path = Path(summary["receipt"])
            self.assertTrue(receipt_path.exists())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

            self.assertEqual(receipt["schema"], "PatchVerificationReceiptV1")
            self.assertIn("check_result", receipt)
            self.assertIn("command", receipt["check_result"])
            self.assertIn("exit_code", receipt["check_result"])
            self.assertEqual(receipt["check_result"]["exit_code"], 0)
            self.assertIn("attribution", receipt)
            self.assertIn("disposition", receipt)
            self.assertEqual(receipt["disposition"], "promote")
            self.assertIn("claim_boundary", receipt)

    def test_fails_open_on_missing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = self._make_repo(base)
            out_dir = base / "receipts"
            result = self._run_verify(
                repo, out_dir, "true", binary_path="/nonexistent/forge-engine"
            )

            self.assertEqual(result.returncode, 0,
                             f"stdout: {result.stdout}, stderr: {result.stderr}")
            combined = result.stdout + result.stderr
            self.assertIn("forge", combined)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["disposition"], "promote")


    def test_write_claim_ledger_marks_receipt_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = self._make_repo(base)
            out_dir = base / "receipts"
            result = subprocess.run([
                sys.executable,
                str(SCRIPT),
                "--repo", str(repo),
                "--claim", "patch compiles and tests pass",
                "--check-cmd", "true",
                "--out-dir", str(out_dir),
                "--no-memory",
                "--write-claim-ledger",
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            summary = json.loads(result.stdout)
            receipt = json.loads(Path(summary["receipt"]).read_text(encoding="utf-8"))
            self.assertIn("claim_ledger", receipt)
            self.assertTrue(receipt["claim_ledger"]["attempted"])
            self.assertIn("available", receipt["claim_ledger"])

    def test_rejects_on_failing_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = self._make_repo(base)
            out_dir = base / "receipts"
            result = self._run_verify(repo, out_dir, "false")

            self.assertEqual(result.returncode, 1,
                             f"stdout: {result.stdout}, stderr: {result.stderr}")
            summary = json.loads(result.stdout)
            self.assertFalse(summary["ok"])
            self.assertEqual(summary["disposition"], "reject")

            receipt_path = Path(summary["receipt"])
            self.assertTrue(receipt_path.exists())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["disposition"], "reject")
            self.assertNotEqual(receipt["check_result"]["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()