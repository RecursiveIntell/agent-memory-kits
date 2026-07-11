# Diagnostic Memory Benchmark Adapters

`shared/scripts/benchmark-diagnostic-memory.py` is a local-only, deterministic adapter framework for the diagnostic benchmark families in the memory epistemics plan. It does not bundle, download, or claim results for any upstream research dataset.

The checked-in fixture bundle is hand-authored and marked `CC0-1.0`. It covers tiny compatibility probes for STALE, A-TMA/LTP, MemTrace, MemConflict, TRUSTMEM/HaluMem transitions, MPBench/GhostWriter-style poisoning, GateMem/GroupMemBench access control, and a MemoryArena-style action loop. Those names describe the adapter target; they do not imply evaluation on the named dataset.

Run the checked-in local probes:

```bash
python shared/scripts/benchmark-diagnostic-memory.py \
  --out docs/benchmarks/diagnostic-memory-local.json
```

Supply independently obtained local fixtures without network activity:

```bash
python shared/scripts/benchmark-diagnostic-memory.py \
  --adapter-fixture stale=/absolute/path/to/stale-fixture.json \
  --out /tmp/diagnostic-memory.json
```

An adapter path may be either a full `DiagnosticMemoryFixtureBundleV1` bundle or a `DiagnosticMemoryAdapterFixtureV1` object with an `adapter` member. A missing, unreadable, or invalid local path is reported as `not_tested`; it is never converted to a pass.

The runner records seven baseline cells: `no_memory`, `full_context`, `bm25`, `dense`, `exact_hybrid`, `witnessed_hybrid`, and `state_resolved`. Each fixture has calibration and held-out cases. The phase taxonomy is emitted independently for ingestion, extraction, transition proposal, verification, commit, indexing, retrieval, rerank, state resolution, evidence sufficiency, admission, answer use, tool arguments, testimony, and forgetting.

Each phase receives ablation credit only when the enabled probe changes an evidence packet, answer, or action and has strictly higher held-out score than its ablated counterpart. The JSON receipt includes local fixture and configuration hashes, Python/platform and git-dirty metadata, raw predictions, confidence intervals, zero-network costs, failures, and explicit `not_tested` entries. A result from these probes is bounded to these deterministic fixtures; it is not a quality claim about an upstream benchmark or an uninstalled competitor.

Machine-readable contracts are in [fixture schema](../../shared/fixtures/schemas/diagnostic-memory-fixture.schema.json) and [receipt schema](../../shared/fixtures/schemas/diagnostic-memory-receipt.schema.json).

## Memory influence and tool-drift subreceipt

The same command embeds a `MemoryInfluenceReceiptV1` under `memory_influence`; it does not create a second reporting channel. Its synthetic CC0 fixture matrix replays `no_memory`, `gold_memory`, `retrieved_memory`, `unlabeled_memory`, `witnessed_state_labeled_memory`, `distractors`, `poison`, and `governed_admission` cells. For every deterministic-ground-truth case it records deltas versus `no_memory` for supported claims, answer quality, unsupported claims, tool choice, tool arguments, risk, latency, and estimated tokens, plus calibration and citation-support measurements.

```bash
python shared/scripts/benchmark-diagnostic-memory.py \
  --memory-influence-fixtures shared/fixtures/memory-influence-fixtures.json \
  --memory-influence-mode offline \
  --out docs/benchmarks/diagnostic-memory-local.json
```

Use `--memory-influence-mode risk_triggered` to evaluate only fixtures whose predeclared risk trigger is true. The runner remains offline and fixture-replay-only (`inference_calls: 0`): it neither invokes nor changes the normal recall-hook path, so it cannot add a second inference to a hook. A case without deterministic ground truth is recorded as `not_tested`, never scored or treated as a quality result.

The [CC0 fixture](../../shared/fixtures/memory-influence-fixtures.json), [fixture schema](../../shared/fixtures/schemas/memory-influence-fixture.schema.json), and [receipt schema](../../shared/fixtures/schemas/memory-influence-receipt.schema.json) define the contract. These measurements are bounded to local deterministic fixtures; they do not claim LLM quality or results on any named benchmark.
