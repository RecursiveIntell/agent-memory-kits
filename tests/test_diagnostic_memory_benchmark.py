#!/usr/bin/env python3
"""Contract tests for the local diagnostic-memory benchmark adapters."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "shared/scripts/benchmark-diagnostic-memory.py"
FIXTURES = ROOT / "shared/fixtures/diagnostic-memory-fixtures.json"
FIXTURE_SCHEMA = ROOT / "shared/fixtures/schemas/diagnostic-memory-fixture.schema.json"
RECEIPT_SCHEMA = ROOT / "shared/fixtures/schemas/diagnostic-memory-receipt.schema.json"
OFFICIAL_STALE = ROOT / ".bench-data/stale/T1_T2_400_FULL.json"
OFFICIAL_SLEEPER = Path("/tmp/sleeper-official")

spec = importlib.util.spec_from_file_location("diagnostic_memory_benchmark", SCRIPT)
assert spec and spec.loader
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class DiagnosticMemoryBenchmarkTests(unittest.TestCase):
    def test_fixture_schema_covers_requested_local_adapter_families(self) -> None:
        bundle = benchmark.load_fixture_bundle(FIXTURES)
        self.assertEqual(bundle["schema"], "DiagnosticMemoryFixtureBundleV1")
        self.assertEqual(
            set(bundle["adapters"]),
            {
                "stale",
                "atma_ltp",
                "memtrace",
                "memconflict",
                "trustmem_halumem",
                "mpbench_ghostwriter",
                "gatemem_groupmembench",
                "memoryarena",
            },
        )
        for adapter in bundle["adapters"].values():
            self.assertEqual(adapter["license"], "CC0-1.0")
            self.assertTrue(adapter["cases"])

    def test_published_schemas_document_fixture_and_receipt_contracts(self) -> None:
        self.assertEqual(json.loads(FIXTURE_SCHEMA.read_text(encoding="utf-8"))["title"], "Diagnostic Memory Fixture Bundle")
        receipt_schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(receipt_schema["title"], "Diagnostic Memory Benchmark Receipt")
        self.assertIn("competitors", receipt_schema["required"])
        self.assertIn("competitors", receipt_schema["properties"])

    def test_competitor_inventory_and_bounded_stale_split_are_predeclared(self) -> None:
        self.assertEqual(
            benchmark.COMPETITOR_IDS,
            ("mem0", "graphiti_zep", "letta", "langmem"),
        )
        rows, _ = benchmark.load_official_stale_dataset(OFFICIAL_STALE)
        projected = [benchmark.project_official_stale_row(row, index) for index, row in enumerate(rows)]
        selected = benchmark.select_competitor_stale_cases(projected)
        self.assertEqual([case["case_index"] for case in selected], [*range(10), *range(100, 110)])
        self.assertEqual({case["split"] for case in selected[:10]}, {"calibration"})
        self.assertEqual({case["split"] for case in selected[10:]}, {"heldout"})

    def test_base_receipt_has_explicit_unmeasured_competitor_records(self) -> None:
        receipt = benchmark.build_diagnostic_report(FIXTURES)
        self.assertEqual(set(receipt["competitors"]), set(benchmark.COMPETITOR_IDS))
        for competitor_id, competitor in receipt["competitors"].items():
            self.assertEqual(competitor["id"], competitor_id)
            self.assertEqual(competitor["status"], "not_tested")
            self.assertIn("reason", competitor)
            self.assertIn("stale", competitor["benchmarks"])
            self.assertIn("sleeper", competitor["benchmarks"])

    def test_letta_worker_is_registered_and_writes_existing_jsonl_receipt(self) -> None:
        cases = [{"case_id": "case-letta", "case_index": 0, "split": "calibration"}]
        rows = [{
            "case_id": "case-letta",
            "case_index": 0,
            "split": "calibration",
            "competitor": "letta",
            "status": "measured",
            "metrics": {"failures": []},
        }]
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            output_path = Path(tmp) / "output.jsonl"
            input_path.write_text(json.dumps(cases), encoding="utf-8")
            with mock.patch.object(benchmark, "_run_letta_worker", return_value=rows) as worker:
                self.assertEqual(benchmark.run_competitor_worker("letta", input_path, output_path), 0)
            worker.assert_called_once_with(cases)
            self.assertEqual(
                [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()],
                rows,
            )

    def test_baseline_matrix_and_phase_local_taxonomy_are_fixed_contracts(self) -> None:
        self.assertEqual(
            benchmark.BASELINE_CELLS,
            (
                "no_memory",
                "full_context",
                "bm25",
                "dense",
                "exact_hybrid",
                "witnessed_hybrid",
                "state_resolved",
            ),
        )
        self.assertEqual(
            benchmark.PHASES,
            (
                "ingestion",
                "extraction",
                "transition_proposal",
                "verification",
                "commit",
                "indexing",
                "retrieval",
                "rerank",
                "state_resolution",
                "evidence_sufficiency",
                "admission",
                "answer_use",
                "tool_arguments",
                "testimony",
                "forgetting",
            ),
        )

    def test_stage_credit_requires_observable_delta_and_heldout_improvement(self) -> None:
        before = {"evidence_packet": ["old"], "answer": "old", "action": "use_old"}
        after = {"evidence_packet": ["new"], "answer": "new", "action": "use_new"}
        credit = benchmark.stage_credit(
            before,
            after,
            heldout_before=0.5,
            heldout_after=1.0,
        )
        self.assertTrue(credit["credited"])
        self.assertTrue(credit["changed_evidence_packet"])
        self.assertTrue(credit["changed_answer"])
        self.assertTrue(credit["changed_action"])
        self.assertEqual(credit["status"], "passed")

        no_delta = benchmark.stage_credit(after, after, heldout_before=0.5, heldout_after=1.0)
        no_gain = benchmark.stage_credit(before, after, heldout_before=1.0, heldout_after=1.0)
        self.assertFalse(no_delta["credited"])
        self.assertFalse(no_gain["credited"])
        self.assertEqual(no_delta["status"], "failed")

    def test_missing_local_adapter_path_is_explicitly_not_tested(self) -> None:
        result = benchmark.resolve_adapter_source(
            "stale", Path("/missing/STALE-fixtures.json"), None
        )
        self.assertEqual(result["status"], "not_tested")
        self.assertIn("reason", result)
        self.assertNotIn("passed", result)

    def test_cli_receipt_has_replay_and_ablation_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "diagnostic.json"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--fixtures", str(FIXTURES), "--out", str(out)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["schema"], "DiagnosticMemoryBenchmarkV1")
            self.assertEqual(set(receipt["baseline_cells"]), set(benchmark.BASELINE_CELLS))
            self.assertIn("environment", receipt)
            self.assertIn("input_hashes", receipt)
            self.assertIn("raw_predictions", receipt)
            self.assertIn("stage_outcomes", receipt)
            self.assertIn("confidence_intervals", receipt)
            self.assertIn("costs", receipt)
            self.assertIn("failures", receipt)
            self.assertEqual(set(receipt["adapters"]), set(benchmark.ADAPTER_IDS))
            for adapter in receipt["adapters"].values():
                self.assertIn(adapter["status"], {"passed", "failed", "not_tested"})
                self.assertIn("dataset", adapter)
                self.assertTrue(adapter["dataset"]["sha256"])
                self.assertIn("stage_ablations", adapter)
                for phase in adapter["stage_ablations"].values():
                    self.assertIn("status", phase)

    def test_cli_marks_explicitly_absent_dataset_not_tested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "diagnostic.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixtures",
                    str(FIXTURES),
                    "--adapter-fixture",
                    "stale=/missing/STALE-fixtures.json",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(receipt["adapters"]["stale"]["status"], "not_tested")
            self.assertTrue(receipt["not_tested"])

    def test_official_stale_pin_split_and_equivalent_event_stream(self) -> None:
        rows, source = benchmark.load_official_stale_dataset(OFFICIAL_STALE)
        self.assertEqual(len(rows), 400)
        self.assertEqual(source["sha256"], f"sha256:{benchmark.OFFICIAL_STALE_SHA256}")
        self.assertEqual(source["repository_commit"], benchmark.OFFICIAL_STALE_REPOSITORY_COMMIT)
        self.assertEqual(source["license"], "CC-BY-4.0")

        projected = benchmark.project_official_stale_row(rows[0], 0)
        self.assertEqual(projected["split"], "calibration")
        self.assertEqual(projected["session_count"], 50)
        self.assertEqual(len(projected["ordered_session_digests"]), 50)
        self.assertEqual(projected["relevant_session_index"], rows[0]["relevant_session_index"])
        self.assertEqual(projected["timestamps"], rows[0]["timestamps"])
        self.assertEqual(projected["M_old"], rows[0]["M_old"])
        self.assertEqual(projected["M_new"], rows[0]["M_new"])
        self.assertEqual(projected["explanation"], rows[0]["explanation"])
        self.assertEqual(projected["probes"], rows[0]["probing_queries"])
        self.assertEqual([event["kind"] for event in projected["material_events"]], ["M_old", "M_new"])
        self.assertEqual(benchmark.project_official_stale_row(rows[99], 99)["split"], "calibration")
        self.assertEqual(benchmark.project_official_stale_row(rows[100], 100)["split"], "heldout")

    def test_official_stale_metrics_and_model_grading_blocker_are_predeclared(self) -> None:
        self.assertEqual(
            benchmark.OFFICIAL_STALE_METRICS,
            (
                "current_state_selection",
                "stale_suppression",
                "conflict_preservation",
                "false_premise_resistance_proxy",
                "action_safe_evidence_packet",
                "historical_reconstruction",
                "abstain_request_evidence_correctness",
                "latency_ms",
                "failures",
            ),
        )
        self.assertEqual(
            benchmark.OFFICIAL_STALE_MODEL_GRADING_BLOCKER,
            "official STALE model grading requires generated responses and the upstream model judge; this no-LLM adapter produced no model responses and made no judge calls",
        )

    def test_official_stale_ranking_projection_has_fixed_multi_candidate_taxonomy(self) -> None:
        rows, _ = benchmark.load_official_stale_dataset(OFFICIAL_STALE)
        projected = benchmark.project_official_stale_ranking_row(rows[0], 0)
        self.assertEqual(projected["split"], "calibration")
        self.assertEqual(
            [candidate["kind"] for candidate in projected["ranking_candidates"]],
            [
                "current_target",
                "stale_predecessor",
                "lexical_distractor",
                "semantic_distractor",
                "unrelated_high_similarity",
                "conflict_candidate",
            ],
        )
        self.assertEqual(
            [candidate["id"] for candidate in projected["ranking_candidates"]],
            [f"{projected['case_id']}:current", f"{projected['case_id']}:stale", f"{projected['case_id']}:lexical", f"{projected['case_id']}:semantic", f"{projected['case_id']}:high_similarity", f"{projected['case_id']}:conflict"],
        )
        self.assertEqual(benchmark.project_official_stale_ranking_row(rows[100], 100)["split"], "heldout")
        self.assertEqual(projected["ranking_policy"]["state_integrity"], "measured separately from candidate ordering")

    def test_ranking_metrics_and_aggregate_are_predeclared_and_state_separate(self) -> None:
        self.assertEqual(
            benchmark.OFFICIAL_STALE_RANKING_METRICS,
            ("recall_at_k", "mrr", "ndcg", "stale_at_rank", "current_vs_stale_ordering", "safe_evidence_rate", "latency_ms", "failures"),
        )
        metrics = benchmark.score_ranking_results(
            expected_current="current",
            expected_stale="stale",
            conflict_candidate="conflict",
            ordered_candidate_ids={"dim1_query": ["current", "stale", "conflict"], "dim2_query": ["stale", "current", "conflict"], "dim3_query": ["current", "conflict", "stale"]},
            latency_ms=2.0,
            failures=[],
        )
        self.assertEqual(metrics["recall_at_k"], {"1": 2 / 3, "3": 1.0, "5": 1.0})
        self.assertAlmostEqual(metrics["mrr"], (1 + 0.5 + 1) / 3)
        self.assertEqual(metrics["current_vs_stale_ordering"], 2 / 3)
        self.assertEqual(metrics["safe_evidence_rate"], 2 / 3)
        aggregate = benchmark.aggregate_ranking_metrics([{"ranking": {"status": "measured", "metrics": metrics}}])
        self.assertEqual(aggregate["ranking"]["metrics"]["recall_at_k"]["1"], {"successes": 2, "total": 3, "rate": 0.666667})
        self.assertEqual(aggregate["ranking"]["metrics"]["state_integrity"], {"status": "separate"})

    def test_official_stale_ranking_cli_reuses_jsonl_and_receipt_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "aggregate.json"
            cases = Path(tmp) / "cases.jsonl"
            markdown = Path(tmp) / "report.md"
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--fixtures", str(FIXTURES),
                    "--official-stale-dataset", str(OFFICIAL_STALE), "--official-stale-limit", "2",
                    "--official-stale-ranking", "--official-stale-cases-out", str(cases),
                    "--markdown-out", str(markdown), "--out", str(out),
                ], capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            ranking = receipt["official_stale"]["ranking"]
            self.assertEqual(ranking["predeclared_metrics"], list(benchmark.OFFICIAL_STALE_RANKING_METRICS))
            self.assertEqual(ranking["aggregate_metrics"]["ranking"]["metrics"]["state_integrity"], {"status": "separate"})
            self.assertEqual(len(cases.read_text(encoding="utf-8").splitlines()), 2)
            self.assertIn("Multi-candidate retrieval ranking", markdown.read_text(encoding="utf-8"))

    def test_official_stale_temporal_separator_crosses_persisted_second_boundary(self) -> None:
        # SQLite fact/edge timestamps are persisted at one-second granularity.
        # A fixed millisecond sleep is therefore not a valid as-of separator.
        self.assertAlmostEqual(benchmark.seconds_to_next_persisted_second(100.25), 0.77)
        self.assertAlmostEqual(benchmark.seconds_to_next_persisted_second(100.99), 0.03)
        self.assertGreater(benchmark.seconds_to_next_persisted_second(100.0), 1.0)

    def test_official_stale_cli_writes_five_case_smoke_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "aggregate.json"
            cases = Path(tmp) / "cases.jsonl"
            markdown = Path(tmp) / "report.md"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixtures",
                    str(FIXTURES),
                    "--official-stale-dataset",
                    str(OFFICIAL_STALE),
                    "--official-stale-limit",
                    "5",
                    "--official-stale-cases-out",
                    str(cases),
                    "--markdown-out",
                    str(markdown),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            stale = receipt["official_stale"]
            self.assertEqual(stale["rows_evaluated"], 5)
            self.assertEqual(stale["split_policy"], {"calibration": [0, 99], "heldout": [100, 399]})
            self.assertEqual(stale["model_grading"]["status"], "not_tested")
            self.assertEqual(stale["model_grading"]["reason"], benchmark.OFFICIAL_STALE_MODEL_GRADING_BLOCKER)
            self.assertEqual(stale["execution"]["llm_calls"], 0)
            self.assertEqual(len(cases.read_text(encoding="utf-8").splitlines()), 5)
            self.assertIn("Official STALE", markdown.read_text(encoding="utf-8"))

    def test_official_sleeper_pin_split_inventory_and_no_inference_contract_are_predeclared(self) -> None:
        source, slices = benchmark.load_official_sleeper_datasets(OFFICIAL_SLEEPER)
        self.assertEqual(source["repository_commit"], "1eb8b7e33b505299155baf3be776545b1620f022")
        self.assertEqual(
            {item["id"]: item["rows"] for item in source["datasets"]},
            {"behavior": 250, "agent_action": 100, "non_english": 100, "benign_save": 70},
        )
        self.assertEqual({name: len(rows) for name, rows in slices.items()}, {"behavior": 250, "agent_action": 100, "non_english": 100, "benign_save": 70})
        self.assertEqual(
            benchmark.OFFICIAL_SLEEPER_CELLS,
            ("ungoverned_append_only", "mutable_latest", "governed_semantic_memory", "no_memory"),
        )
        self.assertIn("attack_success", benchmark.OFFICIAL_SLEEPER_NOT_TESTED_METRICS)
        self.assertIn("model_graded", benchmark.OFFICIAL_SLEEPER_NOT_TESTED_METRICS)

    def test_official_sleeper_no_inference_smoke_writes_row_level_taxonomy(self) -> None:
        receipt, cases = benchmark.run_official_sleeper_adapter(OFFICIAL_SLEEPER, limit_per_slice=1)
        self.assertEqual(receipt["adapter"], "sleeper_official")
        self.assertEqual(receipt["rows_evaluated"], 4)
        self.assertEqual(receipt["execution"]["llm_calls"], 0)
        self.assertEqual(receipt["execution"]["judge_calls"], 0)
        self.assertEqual({case["slice"] for case in cases}, {"behavior", "agent_action", "non_english", "benign_save"})
        self.assertTrue(all("no_write_outcome" in case for case in cases))
        self.assertTrue(all("governed_semantic_memory" in case["cells"] for case in cases))
        self.assertEqual(receipt["model_grading"]["status"], "not_tested")
        no_memory_poison = receipt["aggregate_metrics"]["no_memory"]["metrics"]["poison_memory_retrieval_containment"]
        self.assertEqual(no_memory_poison, {"successes": 3, "total": 3, "rate": 1.0})

    def test_official_sleeper_cli_writes_bounded_smoke_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "aggregate.json"
            cases = Path(tmp) / "cases.jsonl"
            markdown = Path(tmp) / "report.md"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixtures",
                    str(FIXTURES),
                    "--official-sleeper-root",
                    str(OFFICIAL_SLEEPER),
                    "--official-sleeper-limit-per-slice",
                    "1",
                    "--official-sleeper-cases-out",
                    str(cases),
                    "--markdown-out",
                    str(markdown),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            receipt = json.loads(out.read_text(encoding="utf-8"))
            sleeper = receipt["official_sleeper"]
            self.assertEqual(sleeper["rows_evaluated"], 4)
            self.assertEqual(len(cases.read_text(encoding="utf-8").splitlines()), 4)
            self.assertIn("Official Sleeper", markdown.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
