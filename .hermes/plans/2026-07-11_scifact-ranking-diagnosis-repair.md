# Semantic-Memory Scifact Ranking Diagnosis and Repair Plan

> **For Hermes:** Execute with strict RED-GREEN-REFACTOR, calibration/held-out separation, and receipt-backed ablations.

**Goal:** Identify and fix the component responsible for semantic-memory’s poor BEIR Scifact hybrid ranking while preserving temporal, governance, scope, and witnessed-retrieval behavior.

**Measured baseline:** 5,183 documents, 300 official test queries, 339 qrels, `all-minilm:latest` 384d; nDCG@10 0.054714, Recall@10 0.136111, MRR@10 0.032115, zero failures, 60.695 ms mean.

**Architecture:** Reuse the persisted full Scifact store and benchmark receipts. Add a production-supported retrieval-mode selector at the narrowest existing search boundary only if necessary for live ablations. Measure FTS-only, vector-only, and hybrid over a frozen calibration subset before changing ranking. Compare against an exact dense baseline using the same embeddings, then repair only the failing stage and evaluate once on held-out queries.

**Repositories:**
- `/home/sikmindz/Coding/agent-memory-kits`
- `/home/sikmindz/Coding/Libraries/semantic-memory`
- `/home/sikmindz/Coding/Libraries/semantic-memory-mcp` only if the production MCP contract needs a general mode selector

---

## Phase 0: Preserve baseline

1. Record git states and hashes for the benchmark aggregate/per-query receipts.
2. Freeze query split deterministically by sorted official query ID:
   - Calibration: first 100 queries
   - Held-out: remaining 200 queries
3. Do not inspect held-out outcomes while selecting changes.
4. Reuse the existing full store and 5,183-entry ingestion checkpoint.

## Phase 1: Validate benchmark representation

1. RED tests for document construction:
   - marker does not consume the 700-character semantic-text budget;
   - title/body truncation is UTF-8 safe;
   - stable IDs remain extractable without being embedded in searchable content where metadata can carry them.
2. Measure marker-prefix effect on a bounded calibration sample.
3. Measure document truncation variants on calibration only: 700 chars versus the maximum model-safe boundary established by the embedder.
4. Do not rebuild the full corpus unless a representation defect materially changes calibration retrieval.

## Phase 2: Retrieval-mode ablations

1. Expose or invoke existing production modes without duplicating engines:
   - hybrid: existing witnessed retrieval
   - FTS-only: existing `MemoryStore::search_fts_only`
   - vector-only: existing `MemoryStore::search_vector_only`
2. Prefer extending the existing search request with a documented enum over adding separate benchmark-only tools.
3. Preserve namespace filtering, top-k, authority/witness receipts, and deterministic ordering.
4. Add RED contract tests before changing MCP/HTTP surfaces.
5. Run all three modes on the 100-query calibration set and save per-query receipts.

## Phase 3: Exact dense baseline

1. Use the same persisted f32 document embeddings and same query embedder.
2. Compute exact cosine top-10 without RRF/BM25.
3. Verify parity with production vector-only retrieval where exact mode is requested.
4. Report exact dense nDCG@10, Recall@1/5/10, MRR@10, MAP@10, and latency separately.
5. If exact dense is also poor, the blocker is embedding/representation quality—not fusion.

## Phase 4: Root-cause decision

Use the calibration receipts:

- FTS good, vector poor → embedding/document representation repair.
- Vector good, hybrid poor → fusion/RRF repair.
- Both good, hybrid poor → candidate merging/dedup/sort repair.
- All poor → model/domain mismatch or truncation; test a stronger compatible embedding model on calibration.
- Exact dense good, production vector poor → vector backend/index/search defect.

Do not stack fixes. One hypothesis, one RED, one minimal implementation.

## Phase 5: TDD repair

1. Add a focused RED regression reproducing the proven boundary.
2. Implement the smallest general fix.
3. Run focused GREEN, affected Rust/Python suites, and 20-query calibration smoke.
4. Run the full 100-query calibration ablation.
5. Require material improvement over baseline without state-integrity or scope regression.

## Phase 6: Frozen held-out evaluation

1. Freeze code/config/model.
2. Run the 200 held-out queries once.
3. Then run all 300 queries for the final public receipt.
4. Report all modes and the exact claim boundary.
5. Re-run official STALE state-integrity gates and witnessed authority tests.

## Phase 7: Closeout

1. Update the Scifact report and comparative proof.
2. Preserve raw JSON/JSONL receipts and hashes.
3. Commit locally by repository; do not push.
4. Leave `.bench-data/` and `openapi_letta.json` untracked.

## Acceptance criteria

- The failing component is demonstrated by mode-separated receipts.
- Every production change has a RED regression that failed first.
- No held-out tuning or benchmark-label ranking feature.
- Final held-out nDCG@10/Recall@10 materially exceeds the current baseline, or the report identifies a proven embedding/model blocker with no false engine fix.
- Temporal/state integrity, namespace scope, authority, and witnessed receipts do not regress.
