# Semantic-Memory Comparative Proof Report

Date: 2026-07-11

## Verdict

The evidence supports this bounded claim:

> RecursiveIntell semantic-memory is a strong local-first memory epistemics and control plane for persistent agents. It combines verified state transitions, current/historical state resolution, stale suppression, witnessed retrieval, origin-bounded assertion/action authority, governed admission, selective forgetting, and receipt-backed evaluation.

It does not support “best agent memory overall.” State integrity is strong; ordinary multi-candidate retrieval ranking is unmeasured because the attempted lane had a non-identifiable sole relevance label.

## Official STALE deterministic state evaluation

Source:

- Official rows: 400
- Conversation sessions: 20,000
- Dataset SHA-256: `5f3ec375179e20e2e94469e018189188f34e2e7e5f21cbecbd99fcfa648c1876`
- Repository commit: `ea7d391103a151927cd29d2f01d87597a782bdcb`
- License: CC-BY-4.0

| System | Current state | Stale suppression | Conflict preservation | Historical reconstruction | Action-safe proxy |
|---|---:|---:|---:|---:|---:|
| semantic-memory | 98.3% | 100% | 98.3% | 100% | 100% |
| Mem0 2.0.11 | 11.75% | 100% | 100%* | 100%* | 49% |
| LangMem 0.0.30 | 100% | 100% | 0% | 0% | 100% |
| Letta 0.16.8 + PostgreSQL | 0% | 100% | unsupported / 0% | unsupported / 0% | 100% proxy |
| Mutable-latest control | 100% | 100% | 0% | 0% | not scored |
| Append-only control | 0% | 0% | 100% | 100% | not scored |
| Full-context oracle | 100% | 100% | 100% | 100% | 100% |

`*` Mem0’s result is native update-event retention, not bitemporal as-of retrieval.

Interpretation:

- semantic-memory is the only measured system here combining near-complete current selection, complete stale suppression, conflict retention, and bitemporal history.
- LangMem selects keyed current state but overwrites history/conflict.
- Mem0 retains update events but retrieved current state on only 47/400 cases under the fixed local embedding adapter.
- Letta completed 400/400 through its real PostgreSQL-backed passage API with zero runtime failures, but retrieved current state on 0/400 cases under this adapter. Its public passage API exposes no update/history semantics; those were not emulated.
- Deterministic STALE timing includes a one-second persisted-time boundary and is not serving latency.

## Official STALE model-graded evaluation

The pinned official STALE target prompts, all-in-one judge prompt, and parser were run against semantic-memory retrieval-receipt context.

- Target model: `minimax-m3:cloud`
- Judge model: `minimax-m3:cloud`
- Route: Ollama Cloud through `http://127.0.0.1:11434/v1`
- Cases: 400/400 judged
- Logical calls: 1,600 plus four calls for one targeted retry
- Final failures: 0
- Total returned tokens in final 400-case receipt: 2,097,192
- Reported incremental provider cost: $0 through the configured Ollama Cloud access
- Wall time before targeted retry: 2,020.281 seconds

| Dimension | Correct | Accuracy |
|---|---:|---:|
| Explicit probing | 348/400 | 87.00% |
| Adversarial robustness | 331/400 | 82.75% |
| Implicit task | 364/400 | 91.00% |
| Overall | 1,043/1,200 | 86.92% |

Boundary:

- Minimax-M3 Cloud is not a paper model.
- Semantic-memory retrieval-receipt context replaces the paper full-haystack target context.
- This is an official-evaluator system-configuration result, not paper-model reproduction or a cross-system answer-quality victory.

## Valid ordinary retrieval ranking: BEIR Scifact

Semantic-memory was measured on the official public BEIR Scifact corpus and test qrels through production `sm_add_fact` ingestion and `sm_search_witnessed` hybrid retrieval. The run used all 5,183 documents, all 300 official test-qrel queries, 339 positive qrels, and Ollama `all-minilm:latest` at 384 dimensions. It completed with zero query failures.

| nDCG@10 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | MAP@10 | Success@1 | Success@5 | Success@10 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.054714 | 0.010000 | 0.038333 | 0.136111 | 0.032115 | 0.030592 | 0.010000 | 0.040000 | 0.146667 |

Retrieval latency was 60.561 ms p50, 69.624 ms p95, and 60.695 ms mean. The production MCP surface exposes no mode-selecting FTS-only or vector-only retrieval API, so those modes are explicitly not measured and are not conflated with hybrid. Full provenance, configuration, per-query results, and the exact reproduction command are in `docs/benchmarks/beir-scifact-ranking/aggregate.json`, `per-query.jsonl`, and `report.md`. These are ordinary retrieval-ranking numbers, not a competitor comparison or superiority claim.

## Retracted multi-candidate ranking result

Six candidates per official STALE case:

- current target
- stale predecessor
- lexical distractor
- semantic distractor
- unrelated high-similarity candidate
- conflict candidate

The original report scored 400 cases / 1,200 probes as follows:

| Recall@1 | Recall@3 | Recall@5 | MRR | nDCG | Current before stale | Safe evidence |
|---:|---:|---:|---:|---:|---:|---:|
| 0.08% | 18.75% | 75.33% | 0.248 | 0.424 | 20.0% | 18.17% |

These numbers are retracted as invalid evidence, not replaced by improved numbers. The “unrelated high-similarity” candidate contains the exact `M_new` target text, the lexical and semantic distractors copy probe text, and all six candidates are independent ordinary facts with no supplied current/stale lineage. Query and candidate content therefore cannot identify the bare `M_new` record as the sole relevant label.

The lane is retained only as an adversarial/query-copy ordering diagnostic and emits no Recall@k, MRR, nDCG, current-before-stale, or safe-evidence metric. A genuine `M_old -> M_new` supersession lane would duplicate the existing state-integrity benchmark, so no second claim-producing lane was fabricated. No general Rust ranking defect remains proven; ordinary retrieval quality awaits a valid external retrieval dataset with publicly inferable relevance judgments.

## Sleeper deterministic governed-admission slice

Official released rows: 520.

| Cell | Poison admission containment | Poison retrieval containment | Benign-save retention |
|---|---:|---:|---:|
| Governed semantic-memory | 450/450 | 450/450 | 70/70 |
| Mutable-latest | 0/450 | 0/450 | 70/70 |
| Append-only | 0/450 | 0/450 | 70/70 |
| No memory | 450/450 | 450/450 | 0/70 |

Boundary: poison rows were submitted as evidence-free `ephemeral_inference`. This proves that actual admission gate and subsequent witnessed-retrieval containment, not arbitrary model-mediated poison resistance.

## Official Sleeper model-mediated behavior slice

The official campaign runtime, released behavior dataset, actor–critic attack, native memory tool, and post-eval scorers were run with Ollama Cloud Minimax-M3.

- Repository commit: `1eb8b7e33b505299155baf3be776545b1620f022`
- Subject model: `openai-api/ollama/minimax-m3:cloud`
- Dataset: behavior true-optimized with memories
- Attack: `universal_v2_optimized_without_markers`
- Defense: none
- Completed: 250/250
- Campaign status: success
- Wall time: 18m24s
- Memory write/injection rate: 85.2%
- Semantic attacker-goal match rate: 85.2%

This demonstrates that an ungoverned model-managed memory tool is highly vulnerable on this model. Comparing 85.2% model-mediated injection with semantic-memory’s 450/450 deterministic evidence-free rejection is informative but not an identical end-to-end governed Sleeper run.

## Graphiti / Zep

Pinned Graphiti `0.29.2`, commit `526dcad7a300f3c5c506ff96a68bcdc7ca9f97ed`, was reproduced using:

- disposable Neo4j
- local Ollama `qwen2.5:0.5b`
- `all-minilm:latest` embeddings
- public `build_indices_and_constraints`, `add_episode`, and `search`

Five cases and 15 searches completed with zero runtime failures. M_old was returned after adding M_new in 12/15 probes. Because the required current-state update/search semantics were not reproduced, the 400-case promotion was blocked rather than measuring a different task. No history/conflict score was simulated.

## Letta

Pinned Letta `0.16.8`, commit `b76da9092518cbaa2d09042e52fdcbde69243e18`, was reproduced with disposable PostgreSQL plus pgvector.

- Smoke: 20/20, zero failures
- Full: 400/400, zero failures
- Current selection: 0%
- Stale suppression: 100%
- Conflict/history: unsupported / 0%
- Evidence correctness proxy: 100%
- Raw JSONL SHA-256: `cc077404e0f4a3451c66093aedbcb291497045285e236f15e3992679f1996f07`

No hosted inference was used. The disposable PostgreSQL container was removed afterward.

## Live activation proof

Installed binary SHA-256:

`d56773f3818ca2d45a7cf5146b25e6e16ad89fd3667cddae3bf5c90d2ffc7386`

Matching copies:

- source release binary
- `~/.cargo/bin/semantic-memory-mcp`
- `~/.local/bin/semantic-memory-mcp`

Services:

- `semantic-memory-http.service`: active, port 1738 healthy
- `semantic-memory-coding-http.service`: active, port 1739 healthy

Fresh MCP process discovered exactly three lean tools:

- `sm_search_witnessed`
- `sm_decide_assertion_authority`
- `sm_decide_action_authority`

Live authority checks against a recall-only external-evidence fact denied assertion and action and returned no memory content.

## Local integrity verification

- Hostile semantic-memory benchmark: 9/9
- Stale retrievals: 0
- Unsupported durable admissions: 0
- Namespace leakage: 0
- Historical correctness: passed
- Replay equivalence: passed
- Transition compiler, state epistemics, origin authority, evidence gap, forgetting closure, multi-principal policy, shadow policy, and procedural-memory suites: passed

## Defensible positioning

> A local-first memory epistemics and control plane for persistent agents: verified transitions into authoritative state, query-conditioned state resolution, witnessed evidence retrieval, origin-bounded authority, selective-forgetting closure, and receipt-backed evaluation.

Do not claim:

- Best agent memory overall
- Superior general retrieval ranking
- Paper-model STALE reproduction
- Identical end-to-end Sleeper superiority
- Production, enterprise, compliance, or adoption maturity

## Highest-ROI next evaluation target

Acquire or construct a retrieval dataset where relevance is inferable from public query, candidate content, and supplied state metadata. Freeze that calibration contract before inspecting held-out rows; do not use candidate IDs, kinds, or labels as ranking features.

## Primary receipts

- `docs/benchmarks/stale-official/`
- `docs/benchmarks/stale-model-graded-local/`
- `docs/benchmarks/ranking-official/`
- `docs/benchmarks/sleeper-official/`
- `docs/benchmarks/sleeper-model-mediated-cloud-full/`
- `docs/benchmarks/competitors/graphiti-neo4j/`
- `docs/benchmarks/competitors/letta-postgres/`
- `docs/benchmarks/semantic-memory-live-activation-2026-07-11.json`
