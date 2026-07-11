from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/benchmark-beir-scifact-ranking.py"
FIXTURE = ROOT / "tests/fixtures/beir-scifact-tiny/qrels/test.tsv"


def load_benchmark():
    spec = importlib.util.spec_from_file_location("benchmark_beir_scifact_ranking", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BeirScifactRankingTests(unittest.TestCase):
    def test_sorted_query_split_is_deterministic_and_disjoint(self) -> None:
        benchmark = load_benchmark()
        qrels = {str(value): {"d": 1} for value in range(300, 0, -1)}

        calibration = benchmark.select_query_ids(qrels, "calibration")
        heldout = benchmark.select_query_ids(qrels, "heldout")

        self.assertEqual(calibration, sorted(qrels)[:100])
        self.assertEqual(heldout, sorted(qrels)[100:])
        self.assertEqual(len(calibration), 100)
        self.assertEqual(len(heldout), 200)
        self.assertFalse(set(calibration) & set(heldout))

    def test_document_marker_does_not_reduce_semantic_budget_and_is_utf8_safe(self) -> None:
        benchmark = load_benchmark()
        row = {"_id": "42", "title": "Title", "text": "é" * 20}

        content = benchmark.document_content(row, 10)

        self.assertTrue(content.startswith("[beir-scifact-doc-id:42]\n"))
        semantic = content.split("\n", 1)[1]
        self.assertEqual(semantic, "Title\néééé")
        self.assertEqual(len(semantic), 10)

    def test_extract_doc_ids_prefers_metadata_over_content_marker(self) -> None:
        benchmark = load_benchmark()
        payload = {"results": [{"metadata": {"beir_scifact_doc_id": "meta-id"}, "content": "no marker"}]}

        self.assertEqual(benchmark.extract_doc_ids(payload), ["meta-id"])

    def test_cli_accepts_modes_and_query_splits(self) -> None:
        benchmark = load_benchmark()
        parser = benchmark.build_parser()

        args = parser.parse_args(["--mode", "vector_only", "--query-split", "calibration"])

        self.assertEqual(args.mode, "vector_only")
        self.assertEqual(args.query_split, "calibration")

    def test_load_qrels_preserves_multiple_relevant_documents(self) -> None:
        benchmark = load_benchmark()

        qrels, metadata = benchmark.load_qrels(FIXTURE)

        self.assertEqual(qrels, {"q1": {"d1": 1, "d2": 1}, "q2": {"d3": 1}})
        self.assertEqual(metadata["query_count"], 2)
        self.assertEqual(metadata["qrels_count"], 3)
        self.assertRegex(metadata["sha256"], r"^sha256:[0-9a-f]{64}$")

    def test_metric_math_handles_multiple_relevant_documents(self) -> None:
        benchmark = load_benchmark()

        metrics = benchmark.score_query(
            {"d1": 1, "d2": 1},
            ["d2", "d9", "d1"],
            cutoffs=(1, 5, 10),
        )

        self.assertEqual(metrics["recall_at_k"], {"1": 0.5, "5": 1.0, "10": 1.0})
        self.assertEqual(metrics["success_at_k"], {"1": 1.0, "5": 1.0, "10": 1.0})
        self.assertAlmostEqual(metrics["mrr_at_10"], 1.0)
        self.assertAlmostEqual(metrics["map_at_10"], (1.0 + 2.0 / 3.0) / 2.0)
        expected_ndcg = (1.0 + 1.0 / math.log2(4)) / (1.0 + 1.0 / math.log2(3))
        self.assertAlmostEqual(metrics["ndcg_at_10"], expected_ndcg)

    def test_metric_math_scores_missing_results_as_zero(self) -> None:
        benchmark = load_benchmark()

        metrics = benchmark.score_query({"d3": 1}, ["d8", "d9"], cutoffs=(1, 5, 10))

        self.assertEqual(metrics["recall_at_k"], {"1": 0.0, "5": 0.0, "10": 0.0})
        self.assertEqual(metrics["success_at_k"], {"1": 0.0, "5": 0.0, "10": 0.0})
        self.assertEqual(metrics["mrr_at_10"], 0.0)
        self.assertEqual(metrics["map_at_10"], 0.0)
        self.assertEqual(metrics["ndcg_at_10"], 0.0)

    def test_aggregate_uses_all_queries_including_misses(self) -> None:
        benchmark = load_benchmark()
        rows = [
            {"status": "measured", "latency_ms": 10.0, "metrics": benchmark.score_query({"d1": 1}, ["d1"], cutoffs=(1, 5, 10))},
            {"status": "measured", "latency_ms": 30.0, "metrics": benchmark.score_query({"d2": 1}, [], cutoffs=(1, 5, 10))},
        ]

        aggregate = benchmark.aggregate_query_rows(rows, cutoffs=(1, 5, 10))

        self.assertEqual(aggregate["query_count"], 2)
        self.assertEqual(aggregate["failures"], 0)
        self.assertEqual(aggregate["recall_at_k"], {"1": 0.5, "5": 0.5, "10": 0.5})
        self.assertEqual(aggregate["success_at_k"], {"1": 0.5, "5": 0.5, "10": 0.5})
        self.assertEqual(aggregate["mrr_at_10"], 0.5)
        self.assertEqual(aggregate["map_at_10"], 0.5)
        self.assertEqual(aggregate["ndcg_at_10"], 0.5)
        self.assertEqual(aggregate["latency_ms"], {"p50": 20.0, "p95": 29.0, "mean": 20.0})


if __name__ == "__main__":
    unittest.main()
