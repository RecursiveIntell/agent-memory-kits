# Official STALE Deterministic Adapter

- Dataset: `/home/sikmindz/Coding/agent-memory-kits/.bench-data/stale/T1_T2_400_FULL.json` (not copied into tracked files)
- SHA-256: `sha256:5f3ec375179e20e2e94469e018189188f34e2e7e5f21cbecbd99fcfa648c1876`
- Official repository commit: `ea7d391103a151927cd29d2f01d87597a782bdcb`
- License: `CC-BY-4.0`
- Rows: `400`; calibration `100`, held-out `300`
- Per-case sidecar: `/home/sikmindz/Coding/agent-memory-kits/docs/benchmarks/stale-model-graded/deterministic-cases.jsonl` (`sha256:819f9a515a5b3a9ecf14181fb86359001535f590cad60be5459fec8632cdadc4`)
- Target calls: `15`; judge calls: `5`; retries: `40`; failures: `20`

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

- `append_only` — deterministic M_old plus M_new retention with unresolved-conflict abstention
- `full_context_oracle` — deterministic oracle over all 50 ordered session digests and labeled M_old/M_new transition
- `mutable_latest` — deterministic last-write-wins state retaining only M_new; no historical reconstruction
- `no_memory` — empty evidence packet and request-evidence disposition
- `semantic_memory` — actual isolated semantic-memory MCP/core add, supersede, witnessed-current, and historical-as-of path using the existing MCP client

## Aggregate results

| Cell | Current | Stale suppression | Conflict | False-premise proxy | Action-safe packet | History | Abstain/evidence | Mean latency ms | Failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `append_only` | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.0 | 0 |
| `full_context_oracle` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.0 | 0 |
| `mutable_latest` | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.0 | 0 |
| `no_memory` | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.0 | 0 |
| `semantic_memory` | not tested | not tested | not tested | not tested | not tested | not tested | not tested | not tested | 0 |

## Model grading

`not_tested`: OpenRouter rejected every five-case target+judge smoke request with HTTP 403; a credential diagnostic returned "Key limit exceeded (total limit)". The full 400-case run was aborted before scheduling, and no judge score, token count, or cost was synthesized.

## Split and event-stream policy

Rows 0–99 are calibration and rows 100–399 are held out. No parameters are learned and no held-out row is used for tuning. Each row retains all 50 ordered session positions as canonical JSON digests, while the two relevant state events retain their indices, timestamps, M_old, M_new, explanation, and all three probes.

## Exact command

```bash
python3 shared/scripts/benchmark-diagnostic-memory.py --fixtures shared/fixtures/diagnostic-memory-fixtures.json --official-stale-dataset .bench-data/stale/T1_T2_400_FULL.json --official-stale-cases-out docs/benchmarks/stale-model-graded/deterministic-cases.jsonl --official-stale-model-grade --official-stale-retrieval-receipts docs/benchmarks/stale-official/per-case.jsonl --official-stale-evaluator-root /tmp/stale-official --official-stale-model-output-dir docs/benchmarks/stale-model-graded --official-stale-target-model openai/gpt-4o-mini --official-stale-judge-model openai/gpt-4o-mini --official-stale-model-concurrency 10 --official-stale-max-spend-usd 10 --markdown-out docs/benchmarks/stale-model-graded/report.md --out docs/benchmarks/stale-model-graded/aggregate-receipt.json
```

## Claim boundary

No official model-graded score is reported because the five-case target+judge calibration smoke did not complete. The full 400-case run was not started. The requested openai/gpt-4o-mini target and judge via OpenRouter are not paper models, and semantic-memory retrieval-receipt context is not the paper full-haystack target context.
