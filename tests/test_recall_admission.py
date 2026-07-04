#!/usr/bin/env python3
"""Tests for the recall-admission JSONL system with hubness gating."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/recall_admission.py"
spec = importlib.util.spec_from_file_location("recall_admission", SCRIPT)
assert spec and spec.loader
recall_admission = importlib.util.module_from_spec(spec)
sys.modules["recall_admission"] = recall_admission
spec.loader.exec_module(recall_admission)

AdmissionRecord = recall_admission.AdmissionRecord
RecallAdmissionLedger = recall_admission.RecallAdmissionLedger


class RecallAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.ledger_path = self.tmp / "admission.jsonl"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _make_ledger(self) -> RecallAdmissionLedger:
        return RecallAdmissionLedger(self.ledger_path)

    # -- test cases ---------------------------------------------------- #

    def test_admit_candidate(self) -> None:
        """A normal candidate with good score gets admitted=True."""
        ledger = self._make_ledger()
        record = ledger.evaluate(
            query="what is semantic memory",
            result_id="fact:abc-123",
            namespace="research",
            score=0.85,
            cosine=0.90,
            query_terms=["semantic", "memory"],
            result_terms=["semantic", "memory", "retrieval"],
            namespace_match=True,
        )
        self.assertTrue(record.admitted)
        self.assertIsNone(record.reject_reason)
        ledger.write(record)
        s = ledger.stats()
        self.assertEqual(s["total_candidates"], 1)
        self.assertEqual(s["total_admitted"], 1)
        self.assertEqual(s["total_rejected"], 0)

    def test_reject_hub(self) -> None:
        """A high-frequency result (>15 appearances) with low overlap gets rejected."""
        ledger = self._make_ledger()
        result_id = "fact:hub-001"
        # Write 16 records to push the result past the hub threshold
        for i in range(16):
            rec = ledger.evaluate(
                query=f"query {i}",
                result_id=result_id,
                namespace="general",
                score=0.8,
                cosine=0.85,
                query_terms=["alpha"],
                result_terms=["beta", "gamma"],
                namespace_match=False,
            )
            ledger.write(rec)

        # Now evaluate with low overlap — global_hit_frequency will be 16 (>15)
        record = ledger.evaluate(
            query="something unrelated",
            result_id=result_id,
            namespace="general",
            score=0.7,
            cosine=0.72,
            query_terms=["something", "unrelated"],
            result_terms=["completely", "different", "terms"],
            namespace_match=False,
        )
        self.assertFalse(record.admitted)
        self.assertEqual(record.reject_reason, "hub: high frequency with low overlap")
        self.assertGreater(record.global_hit_frequency, 15)

    def test_admit_hub_with_strong_overlap(self) -> None:
        """Hub candidate with strong term overlap and namespace match still admitted."""
        ledger = self._make_ledger()
        result_id = "fact:hub-002"
        # Write 20 records to push well past the hub threshold
        for i in range(20):
            rec = ledger.evaluate(
                query=f"query {i}",
                result_id=result_id,
                namespace="research",
                score=0.75,
                cosine=0.80,
                query_terms=["x"],
                result_terms=["y"],
                namespace_match=False,
            )
            ledger.write(rec)

        # Now evaluate with strong overlap AND namespace match
        record = ledger.evaluate(
            query="semantic memory retrieval",
            result_id=result_id,
            namespace="research",
            score=0.82,
            cosine=0.88,
            query_terms=["semantic", "memory", "retrieval"],
            result_terms=["semantic", "memory", "retrieval", "embedding"],
            namespace_match=True,
        )
        self.assertTrue(record.admitted)
        self.assertIsNone(record.reject_reason)
        self.assertGreater(record.global_hit_frequency, 15)

    def test_reject_low_score(self) -> None:
        """Candidate with score < 0.3 and no namespace match gets rejected."""
        ledger = self._make_ledger()
        record = ledger.evaluate(
            query="low relevance query",
            result_id="fact:low-001",
            namespace="general",
            score=0.15,
            cosine=0.20,
            query_terms=["low", "relevance"],
            result_terms=["unrelated", "content"],
            namespace_match=False,
        )
        self.assertFalse(record.admitted)
        self.assertEqual(record.reject_reason, "low score without namespace match")

    def test_stats(self) -> None:
        """stats() returns correct counts after multiple evaluations."""
        ledger = self._make_ledger()

        # Candidate 1: admitted
        r1 = ledger.evaluate(
            query="q1",
            result_id="r1",
            namespace="ns1",
            score=0.9,
            cosine=0.9,
            query_terms=["a"],
            result_terms=["a"],
            namespace_match=True,
        )
        ledger.write(r1)

        # Candidate 2: rejected low score
        r2 = ledger.evaluate(
            query="q2",
            result_id="r2",
            namespace="ns2",
            score=0.1,
            cosine=0.15,
            query_terms=["b"],
            result_terms=["c"],
            namespace_match=False,
        )
        ledger.write(r2)

        # Candidate 3: admitted (normal)
        r3 = ledger.evaluate(
            query="q3",
            result_id="r3",
            namespace="ns1",
            score=0.75,
            cosine=0.80,
            query_terms=["d"],
            result_terms=["d"],
            namespace_match=True,
        )
        ledger.write(r3)

        s = ledger.stats()
        self.assertEqual(s["total_candidates"], 3)
        self.assertEqual(s["total_admitted"], 2)
        self.assertEqual(s["total_rejected"], 1)
        self.assertEqual(s["unique_result_ids"], 3)
        self.assertEqual(s["hub_result_ids"], [])

    def test_persistence(self) -> None:
        """Records survive across ledger instances (reload from file)."""
        ledger1 = self._make_ledger()
        r1 = ledger1.evaluate(
            query="persist query",
            result_id="fact:persist-001",
            namespace="research",
            score=0.88,
            cosine=0.91,
            query_terms=["persist"],
            result_terms=["persist", "test"],
            namespace_match=True,
        )
        ledger1.write(r1)

        # Create a new ledger instance pointing at the same file
        ledger2 = self._make_ledger()
        s = ledger2.stats()
        self.assertEqual(s["total_candidates"], 1)
        self.assertEqual(s["total_admitted"], 1)

        # The frequency should be loaded from disk
        r2 = ledger2.evaluate(
            query="another query",
            result_id="fact:persist-001",
            namespace="research",
            score=0.85,
            cosine=0.87,
            query_terms=["another"],
            result_terms=["another"],
            namespace_match=True,
        )
        self.assertEqual(r2.global_hit_frequency, 1)
        ledger2.write(r2)

        # A third instance should see 2 records
        ledger3 = self._make_ledger()
        s3 = ledger3.stats()
        self.assertEqual(s3["total_candidates"], 2)
        self.assertEqual(s3["unique_result_ids"], 1)


if __name__ == "__main__":
    unittest.main()