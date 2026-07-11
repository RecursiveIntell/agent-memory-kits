# Memory Trust Kernel Hostile Benchmark

- Schema: `MemoryTrustKernelBenchmarkV1`
- Live surface: `available`

## Predeclared gates

- `state_validity`: `{"max_superseded_leakage": 0.2, "min_superseded_leakage_reduction": 0.8, "no_historical_accuracy_loss": true}`
- `pipeline`: `{"min_stage_specific_receipts": 0.95, "no_failure_as_empty": true}`
- `poisoning`: `{"min_attack_success_reduction": 0.9, "min_benign_retention": 0.95}`
- `reasoning_drift`: `{"aggregate_quality_improves": true, "no_unsafe_action_regression": true}`
- `graph_evidence`: `{"requires_evidence_complete_witnesses": true, "requires_exact_hybrid_baseline": true}`
- `compression`: `{"requires_explicit_degradation": true, "requires_rebuild_and_pointer_rollback": true}`

## Results

- `state_validity`: **pass**
- `pipeline`: **not_tested** — live MCP tool surface exposes no typed fault-injection control; fixed cases are retained as status taxonomy only
- `poisoning`: **pass**
- `reasoning_drift`: **not_tested** — no deterministic quality evaluator is configured; LLM quality is not fabricated
- `graph_evidence`: **not_tested** — witness adapter is intentionally not implemented by this bounded runner
- `compression`: **not_tested** — live MCP tool list exposes no generation/corruption/rebuild/pointer-rollback controls

## Exact command

```bash
python shared/scripts/benchmark-memory-trust-kernel.py --fixtures shared/fixtures/memory-trust-kernel.json --endpoint http://127.0.0.1:1739 --out docs/benchmarks/memory-trust-kernel-live-2026-07-10.json --markdown-out docs/benchmarks/memory-trust-kernel-live-2026-07-10.md --launch-local
```

## Limitations

- No named competitor was installed or run.
- Reasoning-drift is not tested without a deterministic evaluator; this report makes no LLM-quality claim.
- Graph/evidence and compression are not tested unless the live MCP tool list exposes the required witness/recovery controls.
- A pass is only a result from this bounded fixed corpus and temporary server, not a universal trust-kernel claim.
