# Semantic-Memory Comparative Proof Report

Date: 2026-07-11

## Verdict

The current evidence supports this bounded claim:

> RecursiveIntell semantic-memory provides unusually strong deterministic state-integrity behavior for persistent agents: current-state selection, stale suppression, bitemporal historical reconstruction, conflict retention, witnessed retrieval, governed admission, and benign-save preservation.

The evidence does not yet support “best agent memory overall.” Official model-graded answer quality, model-mediated poisoning resistance, multi-candidate ranking, and complete identical runs against Graphiti and Letta remain unproven.

## Official STALE dataset

Source:

- Official rows: 400
- Conversation sessions: 20,000
- Dataset SHA-256: `5f3ec375179e20e2e94469e018189188f34e2e7e5f21cbecbd99fcfa648c1876`
- Repository commit: `ea7d391103a151927cd29d2f01d87597a782bdcb`
- License: CC-BY-4.0
- LLM calls: 0
- Judge calls: 0

| System | Current state | Stale suppression | Conflict preservation | Historical reconstruction | Action-safe proxy |
|---|---:|---:|---:|---:|---:|
| semantic-memory | 98.3% | 100% | 98.3% | 100% | 100% |
| Mem0 2.0.11 | 11.75% | 100% | 100%* | 100%* | 49% |
| LangMem 0.0.30 | 100% | 100% | 0% | 0% | 100% |
| Mutable-latest control | 100% | 100% | 0% | 0% | not scored |
| Append-only control | 0% | 0% | 100% | 100% | not scored |
| Full-context oracle | 100% | 100% | 100% | 100% | 100% |

`*` Mem0’s conflict/history result is its native update-event log retaining old/new values, not bitemporal as-of retrieval.

Interpretation:

- semantic-memory is the only measured system in this run that combined near-complete current-state selection with complete stale suppression and bitemporal history.
- LangMem selected current keyed state perfectly but overwrote historical/conflicting state.
- Mem0 retained update events but retrieved the new state on only 47 of 400 deterministic probes under this adapter’s fixed local embedding.
- Each competitor case contained one keyed current item after update. This is a state/update/search proxy, not a multi-candidate ranking benchmark.
- semantic-memory latency in the official STALE harness is dominated by the required one-second persisted timestamp boundary. It is not serving latency.

## Official Sleeper deterministic slice

Source:

- Repository commit: `1eb8b7e33b505299155baf3be776545b1620f022`
- Rows: 520
  - Behavior poison: 250
  - Agent-action poison: 100
  - Non-English poison: 100
  - Benign save: 70
- LLM calls: 0
- Judge calls: 0

| Cell | Poison admission containment | Poison retrieval containment | Benign-save retention |
|---|---:|---:|---:|
| Governed semantic-memory | 450/450 | 450/450 | 70/70 |
| Mutable-latest | 0/450 | 0/450 | 70/70 |
| Append-only | 0/450 | 0/450 | 70/70 |
| No memory | 450/450 | 450/450 | 0/70 |

Boundary:

- Poison rows were submitted as evidence-free `ephemeral_inference` to the actual MCP admission gate.
- This proves deterministic rejection and subsequent retrieval containment for that class.
- It does not prove official Sleeper attack-success, semantic score, model response quality, model-mediated poisoning resistance, or purpose-specific assertion/action containment.

## Named competitor execution

### Measured

- Mem0 `2.0.11`, commit `c9af55986e4a31aa98931b6b909d5639e9b2013a`
  - 400/400 rows measured
  - Zero runtime failures
  - Fixed local SHA-256-derived 16-dimensional embedding
  - No hosted service, LLM, or judge calls

- LangMem `0.0.30`, commit `c01e273b94aa4c06e41d0ed1ccce0db17de2bc11`
  - 400/400 rows measured
  - Zero runtime failures
  - Same fixed local embedding policy
  - No hosted service, LLM, or judge calls

### Not tested after bounded attempts

- Graphiti / Zep `0.29.2`, commit `526dcad7a300f3c5c506ff96a68bcdc7ca9f97ed`
  - Installation succeeded.
  - Public `Graphiti.add_episode` reached local Ollama and Kuzu.
  - Runtime failed because Kuzu lacked the expected `edge_name_and_fact` FTS index.
  - Rows measured: 0.

- Letta `0.16.8`, commit `b76da9092518cbaa2d09042e52fdcbde69243e18`
  - Isolated 241-package installation succeeded after adding `asyncpg`.
  - Settings reported SQLite, but both documented startup paths initialized PostgreSQL and attempted localhost:5432.
  - No PostgreSQL service was provisioned solely for the benchmark.
  - Rows measured: 0.

Neither blocked competitor received simulated results.

## Local integrity verification

- Hostile semantic-memory benchmark: 9/9
- Stale retrievals: 0
- Unsupported durable admissions: 0
- Namespace leakage: 0
- Historical correctness: passed
- Replay equivalence: passed

The broader implementation also has controller receipts for transition verification, state epistemics, origin authority, evidence-gap retrieval, forgetting closure, multi-principal policy, shadow policy, and procedural memory. Those local tests are evidence for those components, not competitor superiority.

## Defensible positioning

Strongest defensible thesis:

> A local-first memory epistemics and control plane for persistent agents: verified transitions into authoritative state, query-conditioned state resolution, witnessed evidence retrieval, origin-bounded authority, selective-forgetting closure, and receipt-backed evaluation.

Do not claim yet:

- Best agent memory overall
- Highest answer quality
- Superior retrieval ranking generally
- Official STALE model-graded victory
- Official Sleeper attack-success victory
- Superiority to Graphiti or Letta
- Production or enterprise maturity

## Next proof gates

1. Run the official model-graded STALE response evaluator with a predeclared provider/model and cost cap.
2. Run model-mediated Sleeper subject/manager/judge evaluation.
3. Expose and test purpose-specific assertion/action decisions through the MCP surface.
4. Reproduce Graphiti with a supported graph backend or upstream-fixed Kuzu setup.
5. Reproduce Letta with its required PostgreSQL service in a disposable container.
6. Add multi-candidate retrieval ranking cases so state integrity and retrieval quality are measured separately.

## Primary receipts

- `docs/benchmarks/stale-official/aggregate-receipt.json`
- `docs/benchmarks/stale-official/per-case.jsonl`
- `docs/benchmarks/stale-official/report.md`
- `docs/benchmarks/sleeper-official/aggregate-receipt.json`
- `docs/benchmarks/sleeper-official/per-case.jsonl`
- `docs/benchmarks/sleeper-official/report.md`
- `docs/benchmarks/competitors/aggregate-receipt.json`
- `docs/benchmarks/competitors/stale-mem0-per-case.jsonl`
- `docs/benchmarks/competitors/stale-langmem-per-case.jsonl`
- `docs/benchmarks/competitors/blockers.json`
- `docs/benchmarks/competitors/environment-and-commands.md`
