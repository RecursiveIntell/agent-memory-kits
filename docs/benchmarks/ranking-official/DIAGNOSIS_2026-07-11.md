# Semantic-Memory Ranking Repair Diagnosis - 2026-07-11

## Scope

Phase 1 bounded pass. Diagnosis used official STALE calibration rows 0-4 and the previously inspected calibration aggregate for rows 0-99 only. No held-out outcome was inspected and no held-out tuning was performed.

## Final Contract Repair Decision

The six-candidate lane is non-identifiable and is no longer claim-producing. A contract audit now proves both defects before scoring: `unrelated_high_similarity` contains the exact `M_new` target semantics, while the lexical and semantic distractors copy `dim1_query` and `dim3_query`. Claim-producing scoring refuses this candidate set with `ValueError`; the runnable lane is explicitly `adversarial_query_copy_diagnostic`, retains ordered IDs and latency for diagnosis, and emits an empty metric list.

The prior 400-row result (Recall@1 0.08%, Recall@3 18.75%, Recall@5 75.33%, MRR 0.248, nDCG 0.424, current-before-stale 20.0%, safe evidence 18.17%) is retracted as invalid evidence. It is retained in historical artifacts for audit and is not silently overwritten.

No replacement claim-producing lane was added. Genuine `M_old -> M_new` supersession/current-state operations are already exercised by the existing `semantic_memory` state-integrity cell; presenting the same operation as a new ranking benchmark would duplicate that proof. Ordinary retrieval quality therefore remains unmeasured pending a valid external retrieval dataset whose relevance is inferable from supplied public state.

The additive Rust explained-fusion API and the permanently ignored desired-ordering RED were removed. They were useful during diagnosis but are not durable product requirements after the invalid benchmark contract was rejected; retaining the ignored test would assert unproven behavior. Semantic-memory Rust ranking behavior is unchanged.

## Evidence

- Benchmark construction: `project_official_stale_ranking_row` creates six ordinary facts: current `M_new`, stale `M_old`, lexical query-copy distractor, semantic query-copy distractor, high-similarity candidate containing `M_new`, and conflict candidate containing `M_old`.
- Insertion/retrieval path: `_semantic_memory_ranking_case` inserts each candidate with `sm_add_fact`, then calls `sm_search_witnessed` with `top_k=6` and extracts predeclared candidate IDs only from returned result content.
- Score calculation: `score_ranking_results` scores only candidate ordering, with `current_target` as the sole relevant item. State integrity and supersession are explicitly separate.
- MCP/Rust path: `sm_search_witnessed` calls `MemoryStore::search_with_context` with `ExactnessProfile::PreferExact`. Rust hybrid search builds BM25 and vector candidate pools, fuses with RRF, sorts final scores descending, and returns the store order unchanged through MCP.
- Calibration rows 0-99 show a deterministic failure pattern:
  - `dim1_query`: top result was `lexical_distractor` in 100/100 rows.
  - `dim3_query`: top result was `semantic_distractor` in 100/100 rows.
  - `dim2_query`: top result was `stale_predecessor` in 84/100 rows, `lexical_distractor` in 13/100, and `semantic_distractor` in 3/100.
  - Current target Recall@1 was 0/300 probes on calibration rows.
- First calibration case confirms current was inserted first but ranked last for `dim1_query`; the top rank followed query-copy content, not insertion order.
- Harness mismatch: `run_official_stale_adapter(..., launch_local=True, ranking=True)` forced `SEMANTIC_MEMORY_EMBEDDER=mock`. That was real harness hygiene and was corrected, but it was not sufficient and is not the primary ranking root cause.
- Fresh real-Candle baseline over calibration rows 0-4 (15 probes): Recall@1 0/15, Recall@3 2/15, Recall@5 7/15, MRR 0.210, nDCG 0.39436, current-before-stale 4/15, safe evidence 2/15. Artifacts: `/tmp/ranking-candle-smoke.json` and `/tmp/ranking-candle-smoke-cases.jsonl`.
- `RrfCandidate::explained` preserves raw SQLite BM25 score, BM25 rank, cosine similarity, vector rank, and the two reciprocal-rank contributions in `ScoreBreakdown`. The final score uses only ranks for the retrieval terms: `weight / (k + rank)`, with default `k=60` and equal BM25/vector weights. Raw score magnitude is exposed but does not affect fusion.
- A focused controlled RED demonstrated the rank-only failure: a semantic target at vector rank 1 lost to a query copy at BM25 rank 1/vector rank 2 solely because the latter received two near-equal RRF contributions. The RED failed at the intended ordering assertion after compiling.
- The one-variable candidate fix averaged active retrieval-lane contributions. It made the controlled regression GREEN and retained the raw score/rank/contribution receipt fields, but a rebuilt release MCP real-Candle smoke produced exactly the same ordering and metrics as baseline. The fix was therefore rejected and reverted rather than combined with another speculative scorer.
- Calibration fixture inspection shows why that RRF weakness is insufficient: all six candidates are inserted as ordinary independent facts. The expected `current_target` has no lineage/current-state relation to `stale_predecessor`, and the ranker receives no benchmark explanation or session ordering. Several probes repeat the stale claim or are vague recommendation questions, while the lexical/semantic distractors copy those queries verbatim and the high-similarity distractor copies `M_new`. Candidate content plus query alone does not contain a general, non-label signal that identifies the bare `M_new` record as the sole relevant item.

## Root Cause

The primary failure is a task/retrieval-contract mismatch, not the mock embedder and not a proven general scorer defect. The benchmark defines relevance as "the current state record" but presents the six ranking candidates to semantic-memory as unrelated ordinary facts. The Rust ranking layer cannot infer hidden update lineage or recency from query/content when those signals are absent. Query-copy distractors are correctly high under lexical and semantic similarity for the text actually supplied.

Rank-only RRF with `k=60` and equal weights is independently ruled in as a general weakness because it erases score magnitude and rewards candidates returned by both lanes. However, removing that reward did not change any of the 15 real-Candle smoke rankings, so it is not the actual cause of this benchmark result.

## Ruled Out Or Deprioritized

- Reversed ordering: ruled out by Rust `rrf_fuse_detailed_with_context`, which sorts final score descending. BM25 raw scores are correctly ordered ascending before rank conversion because SQLite FTS5 lower BM25 is better.
- Result extraction reversal: ruled out by `_candidate_ids_from_payload`, which iterates MCP `results` in order.
- Pre-fusion truncation: ruled out for this fixture because `candidate_pool_size=50` and each namespace has only six candidates.
- Insertion-order bias: ruled out for the observed top failures because current is inserted first, while calibration top results are lexical/semantic/stale depending on probe content.
- Candidate ID/kind leakage: no fix used candidate ID, candidate kind, expected label, or case ID as a ranking feature.
- Mock embeddings as primary cause: ruled out by identical poor metrics under the real Candle embedder.
- Active-lane RRF summation as sufficient cause: ruled out by the unchanged before/after real-MCP smoke.

## Fix

The earlier harness correction remains valid: `semantic_memory_launch_env(...)` makes the official STALE ranking path use a real semantic embedder by default:

- non-ranking isolated semantic-memory runs still use `SEMANTIC_MEMORY_EMBEDDER=mock`;
- ranking runs use `SEMANTIC_MEMORY_RANKING_EMBEDDER` when provided, otherwise `candle`;
- candidate construction, scoring, extraction, split policy, and task labels are unchanged.

No ranking behavior fix is retained from this pass. The smallest tested Rust change did not improve the real-MCP smoke and was reverted. The remaining non-cheating resolution is to make the benchmark exercise genuine semantic-memory state metadata (real supersession/current lineage) or redefine ordinary retrieval relevance from information actually present in query and candidate content. Either changes the benchmark contract and requires an explicit decision before further Rust ranking work.

No additive Rust API or ignored ranking RED is retained; neither is needed by the repaired benchmark contract.

## Commands Run

Final contract RED (before implementation):

```text
python3 -m unittest discover -s tests -p 'test_diagnostic_memory_benchmark.py' -k non_identifiable

ERROR: module has no attribute assess_ranking_contract
ERROR: module has no attribute score_claim_producing_ranking
FAILED (errors=2)
```

Final contract GREEN and focused suites:

```text
non_identifiable: 2 passed
claim_producing: 1 passed
ranking_cli: 1 passed
official_stale: 9 passed
test_benchmark_recall.py: 5 passed
test_benchmark_compaction.py: 3 passed
```

The full `test_diagnostic_memory_benchmark.py` file reached 26 passing tests and three unrelated official-Sleeper fixture failures because `/tmp/sleeper-official` was not a Git checkout. The focused official-STALE suite is complete.

Five-case real-Candle smoke:

```text
rows=5; status=diagnostic_only; failures=0; predeclared_metrics=[]
contract=non_identifiable
violations=duplicate_target_semantics,query_copy_leakage
```

Receipts:

- `contract-smoke-aggregate.json` — `sha256:eefcde5f35beba0affee70cd0817ae5a8294e83e0fa16ea637feff7d0a6b8ef8`
- `contract-smoke-per-case.jsonl` — `sha256:f8f0c6b0f363f7fd4336801e2c3b652f9028d5850b7cc27fbb1771f78503be24`
- `contract-smoke-report.md` — `sha256:5794f577f97f125dc1570eaea6e89b4a58ca661f1035c0a10d6af163d2db9ed3`
- `RETRACTION_2026-07-11.json` preserves the old result as `invalid_evidence`.

`DiagnosticMemoryBenchmarkV1` schema validation, retraction JSON parsing, Python compilation, both repository `git diff --check` checks, and Rust-worktree cleanliness passed. The 100-row calibration run was not started because no contract-valid scoring lane exists. Held-out rows were not inspected.

RED:

```text
python3 -m unittest discover -s tests -p 'test_diagnostic_memory_benchmark.py' -k test_official_stale_ranking_launch_does_not_force_mock_embeddings

ERROR: test_official_stale_ranking_launch_does_not_force_mock_embeddings
AttributeError: module 'diagnostic_memory_benchmark' has no attribute 'semantic_memory_launch_env'
FAILED (errors=1)
```

GREEN:

```text
python3 -m unittest discover -s tests -p 'test_diagnostic_memory_benchmark.py' -k test_official_stale_ranking_launch_does_not_force_mock_embeddings
.
Ran 1 test in 0.001s
OK
```

Engine RED (before the attempted scorer change):

```text
cargo test --test search_tests hybrid_fusion_does_not_reward_query_copy_for_merely_appearing_in_both_lanes -- --exact --nocapture

assertion failed: expected semantic target at rank 1
FAILED. 0 passed; 1 failed
```

Attempted-fix GREEN:

```text
test hybrid_fusion_does_not_reward_query_copy_for_merely_appearing_in_both_lanes ... ok
test rrf_fusion_order ... ok
test explainable_search_matches_configured_rrf_math ... ok
```

Affected suites while the hypothesis was active:

```text
cargo test --test search_tests --test hardening_semantics
45 passed; 0 failed
```

Real MCP/Candle smoke after the attempted fix:

```text
Recall@1 0/15; Recall@3 2/15; Recall@5 7/15; MRR 0.210;
nDCG 0.39436; current-before-stale 4/15; safe evidence 2/15
```

This was identical to baseline, so the behavior change was reverted. The now-unjustified ignored RED was removed. No rows 100-399 and no 100-row calibration run were executed.

Focused existing check:

```text
python3 -m unittest discover -s tests -p 'test_diagnostic_memory_benchmark.py' -k test_official_stale_ranking_cli_reuses_jsonl_and_receipt_schema
.
Ran 1 test in 7.555s
OK
```

Diff hygiene:

```text
git diff --check -- shared/scripts/benchmark-diagnostic-memory.py tests/test_diagnostic_memory_benchmark.py
```

No output.

## Files Changed

- `shared/scripts/benchmark-diagnostic-memory.py`
- `tests/test_diagnostic_memory_benchmark.py`
- `docs/benchmarks/ranking-official/DIAGNOSIS_2026-07-11.md`
- `docs/benchmarks/SEMANTIC_MEMORY_COMPARATIVE_PROOF_2026-07-11.md`
- `shared/fixtures/schemas/diagnostic-memory-receipt.schema.json`
- `docs/benchmarks/ranking-official/report.md`
- `docs/benchmarks/ranking-official/contract-smoke-aggregate.json`
- `docs/benchmarks/ranking-official/contract-smoke-per-case.jsonl`
- `docs/benchmarks/ranking-official/contract-smoke-report.md`

## Not Changed

- No semantic-memory ranking behavior or durable API was changed; the Rust worktree is clean after removing the diagnostic leftovers.
- No benchmark task labels, expected IDs, candidate IDs, candidate kinds, or held-out rows were used as ranking features.
- Existing unrelated untracked `.bench-data/`, `docs/benchmarks/ranking-official/receipts/`, and `openapi_letta.json` were preserved.
