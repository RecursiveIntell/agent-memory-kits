# Semantic-Memory Ranking Repair Implementation Plan

> **For Hermes:** Execute this plan with strict RED-GREEN-REFACTOR discipline and preserve raw receipts for every benchmark run.

**Goal:** Materially improve held-out multi-candidate retrieval ranking without weakening temporal/state integrity, governance, scope isolation, or claim boundaries.

**Architecture:** First prove whether the 0.08% Recall@1 result comes from the benchmark fixture, score extraction, candidate generation, embedding configuration, or semantic-memory’s hybrid ranker. Then add the smallest general retrieval fix at the owning layer. Tune only on official STALE rows 0–99, freeze parameters, and evaluate once on rows 100–399.

**Tech Stack:** Python benchmark harness and unittest; Rust semantic-memory hybrid retrieval; SQLite FTS/vector search; MCP witnessed retrieval; JSON/JSONL benchmark receipts.

---

## Non-negotiable boundaries

- Do not use candidate IDs, candidate kinds, expected labels, case indices, or held-out answers as ranking features.
- Do not modify held-out rows 100–399 based on observed outcomes.
- Do not weaken supersession, stale suppression, namespace filtering, authority, witnessed-retrieval receipts, or evidence controls.
- Preserve raw lexical/vector/component scores and deterministic tie-break information in local receipts.
- Treat benchmark defects and engine defects separately; do not improve metrics by silently changing the task.
- No push. Commit locally only after verification.

## Phase 0: Preserve baseline and working-tree receipts

1. Save scoped `git status`, `git diff --stat`, and relevant commit IDs for:
   - `/home/sikmindz/Coding/agent-memory-kits`
   - `/home/sikmindz/Coding/Libraries/semantic-memory`
   - `/home/sikmindz/Coding/Libraries/semantic-memory-mcp`
2. Preserve the current official ranking aggregate and per-case digests.
3. Record baseline metrics: Recall@1 0.08%, Recall@3 18.75%, Recall@5 75.33%, MRR 0.248, nDCG 0.424, current-before-stale 20.0%, safe evidence 18.17%.

## Phase 1: Root-cause diagnosis

1. Trace `project_official_stale_ranking_row` → `_semantic_memory_ranking_case` → MCP `sm_search_witnessed` → semantic-memory hybrid candidate generation/reranking.
2. On calibration rows 0–99 only, capture for every candidate/probe:
   - lexical score and lexical rank
   - vector score and vector rank
   - fused score and final rank
   - deterministic tie-break fields
   - result inclusion/exclusion reason
3. Add benchmark tests proving marker extraction does not alter semantic content scoring.
4. Add tests proving candidate insertion order does not control final order.
5. Check for reversed sorting, score-domain mismatch, missing normalization, truncation before fusion, ID extraction loss, and embedding-model mismatch.
6. Produce a diagnosis receipt naming the first failing boundary and ruled-out alternatives.

## Phase 2: RED regressions

1. Add a focused engine-level regression where a relevant current fact must outrank:
   - lexical query-copy distractor
   - semantic distractor
   - unrelated high-similarity candidate
   - stale/conflicting candidate when real lineage metadata exists
2. Add a benchmark-level RED test using calibration fixtures only.
3. Run focused tests and preserve expected failures before production changes.

Likely files:
- `/home/sikmindz/Coding/agent-memory-kits/tests/test_diagnostic_memory_benchmark.py`
- `/home/sikmindz/Coding/agent-memory-kits/shared/scripts/benchmark-diagnostic-memory.py`
- `/home/sikmindz/Coding/Libraries/semantic-memory/src/search.rs`
- relevant Rust search tests under `/home/sikmindz/Coding/Libraries/semantic-memory/tests/`

## Phase 3: Minimal general fix

Depending on Phase 1 evidence, implement exactly one smallest owning-layer correction:

- Correct ordering/normalization/extraction bug, or
- Fair candidate pooling before fusion, or
- Calibrated lexical/vector fusion with deterministic tie-breaking, or
- State-aware reranking only when genuine lineage/current-state metadata exists.

Do not add a benchmark-specific candidate-kind boost.

## Phase 4: Calibration ablations

On rows 0–99 only:

1. Run baseline.
2. Run one-variable ablations for each proposed score component.
3. Freeze the smallest configuration that materially improves Recall@1 and MRR.
4. Require no regression in stale suppression, namespace scope, authority, or witnessed receipts.
5. Save machine-readable calibration receipts.

## Phase 5: Held-out evaluation

1. Freeze code and parameters before reading held-out outcomes.
2. Run rows 100–399 once.
3. Report Recall@1/3/5, MRR, nDCG, current-before-stale, safe evidence, latency, and confidence intervals where supported.
4. Rerun official deterministic STALE state-integrity gates.
5. Run affected Python and Rust suites, schema validation, and `git diff --check`.

## Phase 6: Report and local commits

1. Update `/home/sikmindz/Coding/agent-memory-kits/docs/benchmarks/SEMANTIC_MEMORY_COMPARATIVE_PROOF_2026-07-11.md` with before/after results and exact claim boundary.
2. Write a diagnosis/ablation receipt under `docs/benchmarks/ranking-official/` or an ignored receipt directory as appropriate.
3. Commit independently by repository with precise messages.
4. Leave disposable `.bench-data/` and `openapi_letta.json` uncommitted unless explicitly required.
5. Do not push.

## Acceptance criteria

- Root cause is demonstrated with raw score/order evidence, not inferred from aggregate metrics.
- A RED regression fails before the fix and passes after it.
- Held-out Recall@1 and MRR improve materially over 0.08% and 0.248.
- Deterministic STALE state integrity does not regress from the existing measured rates.
- No candidate-label leakage or held-out tuning.
- All affected tests and receipt validators pass.
- Final report distinguishes ordinary ranking, state integrity, and model-mediated answer quality.
