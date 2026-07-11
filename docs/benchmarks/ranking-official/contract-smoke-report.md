# Official STALE Deterministic Adapter

- Dataset: `.bench-data/stale/T1_T2_400_FULL.json` (not copied into tracked files)
- SHA-256: `sha256:5f3ec375179e20e2e94469e018189188f34e2e7e5f21cbecbd99fcfa648c1876`
- Official repository commit: `ea7d391103a151927cd29d2f01d87597a782bdcb`
- License: `CC-BY-4.0`
- Rows: `5`; calibration `5`, held-out `0`
- Per-case sidecar: `docs/benchmarks/ranking-official/contract-smoke-per-case.jsonl` (`sha256:f8f0c6b0f363f7fd4336801e2c3b652f9028d5850b7cc27fbb1771f78503be24`)
- LLM calls: `0`; judge calls: `0`

## Predeclared metrics

- `current_state_selection`
- `stale_suppression`
- `conflict_preservation`
- `false_premise_resistance_proxy`
- `action_safe_evidence_packet`
- `historical_reconstruction`
- `abstain_request_evidence_correctness`
- `latency_ms`
- `failures`

## Baseline definitions

- `semantic_memory` — actual isolated semantic-memory MCP/core add, supersede, witnessed-current, and historical-as-of path using the existing MCP client
- `mutable_latest` — deterministic last-write-wins state retaining only M_new; no historical reconstruction
- `append_only` — deterministic M_old plus M_new retention with unresolved-conflict abstention
- `no_memory` — empty evidence packet and request-evidence disposition
- `full_context_oracle` — deterministic oracle over all 50 ordered session digests and labeled M_old/M_new transition

## Aggregate results

| Cell | Current | Stale suppression | Conflict | False-premise proxy | Action-safe packet | History | Abstain/evidence | Mean latency ms | Failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `semantic_memory` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 803.888702 | 0 |
| `mutable_latest` | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.0 | 0 |
| `append_only` | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.0 | 0 |
| `no_memory` | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.0 | 0 |
| `full_context_oracle` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.0 | 0 |

## Adversarial/query-copy diagnostic (not a ranking metric)

- Candidate kinds: `current_target`, `stale_predecessor`, `lexical_distractor`, `semantic_distractor`, `unrelated_high_similarity`, `conflict_candidate`
- Contract: `non_identifiable`; violations: `duplicate_target_semantics`, `query_copy_leakage`.
- Retraction: `Recall@1 0.08%, Recall@3 18.75%, Recall@5 75.33%, MRR 0.248, nDCG 0.424` is `invalid_evidence` because the sole relevant label is non-identifiable from supplied query/content/public state.
- Claim boundary: no Recall@k, MRR, nDCG, current-before-stale, or safe-evidence metric is emitted; ordinary ranking quality remains unmeasured

## Model grading

`not_tested`: official STALE model grading requires generated responses and the upstream model judge; this no-LLM adapter produced no model responses and made no judge calls.

## Split and event-stream policy

Rows 0–99 are calibration and rows 100–399 are held out. No parameters are learned and no held-out row is used for tuning. Each row retains all 50 ordered session positions as canonical JSON digests, while the two relevant state events retain their indices, timestamps, M_old, M_new, explanation, and all three probes.

## Exact command

```bash
python3 shared/scripts/benchmark-diagnostic-memory.py --fixtures shared/fixtures/diagnostic-memory-fixtures.json --official-stale-dataset .bench-data/stale/T1_T2_400_FULL.json --official-stale-limit 5 --official-stale-ranking --official-stale-launch-local --official-stale-cases-out docs/benchmarks/ranking-official/contract-smoke-per-case.jsonl --markdown-out docs/benchmarks/ranking-official/contract-smoke-report.md --out docs/benchmarks/ranking-official/contract-smoke-aggregate.json
```

## Claim boundary

These are deterministic state/evidence measurements and proxies. They are not official response-accuracy scores and make no model-quality or competitor-superiority claim.
