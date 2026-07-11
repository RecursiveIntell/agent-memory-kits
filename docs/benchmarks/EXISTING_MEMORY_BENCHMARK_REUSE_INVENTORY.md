# Existing Memory Benchmark Reuse Inventory

Purpose: mandatory preflight for STALE, Sleeper, competitor, and comparative-proof work. Extend these surfaces; do not recreate them.

## Existing benchmark runners

- `shared/scripts/benchmark-diagnostic-memory.py`
  - Owns `DiagnosticMemoryBenchmarkV1`
  - Baseline-cell matrix
  - Phase ablations
  - Explicit `not_tested`
  - Raw predictions, costs, failures, environment and source hashes
  - Competitor result field
  - `MemoryInfluenceReceiptV1`
- `shared/scripts/benchmark-memory-trust-kernel.py`
  - Owns the existing MCP client pattern
  - StateValidityBench and poisoning/governance patterns
- `shared/scripts/benchmark-recall.py`
  - Existing generic retrieval/recall benchmark; do not create another
- `shared/scripts/benchmark-retrieval.py`
- `shared/scripts/benchmark-compaction-cross-engine.py`
- `shared/scripts/benchmark-context-governor.py`
- `shared/scripts/benchmark-recall-receipted.sh`

## Existing schemas and fixtures

Extend `shared/fixtures/schemas/`; do not create a parallel schema family.

Existing fixture bundles include:

- `shared/fixtures/diagnostic-memory-fixtures.json`
- `shared/fixtures/memory-influence-fixtures.json`
- `shared/fixtures/memory-trust-kernel.json`

Official upstream datasets stay under `.bench-data/` and must not be copied into tracked source or documentation.

## Existing tests to extend

- `tests/test_diagnostic_memory_benchmark.py`
- `tests/test_memory_influence.py`
- `tests/test_memory_trust_kernel_bench.py`
- `tests/test_benchmark_recall.py`

Add focused tests only for genuinely missing adapter behavior.

## Existing semantic-memory core contracts

Located in `/home/sikmindz/Coding/Libraries/semantic-memory`:

- `MemoryAuthority`
- `StateView`
- `StateResolutionReceiptV1`
- `PremiseStatus`
- `AnswerDisposition`
- `StateDependencyEdgeV1`
- `EvidenceGapV1`
- `EvidencePacketV1`
- Verified memory-transition compiler and quarantine
- Origin-bound recall/assertion/action authority
- Multi-principal governance
- Selective-forgetting closure
- Shadow-policy governance
- Procedural-memory artifacts
- Witnessed retrieval and authority receipts

Benchmark-adapter tasks must not add or modify Rust core contracts unless a controller-confirmed missing capability blocks a real upstream benchmark.

## Active runtime already in place

- Installed `semantic-memory-mcp` binaries under `~/.cargo/bin` and `~/.local/bin`
- Active HTTP services on ports 1738 and 1739
- Lean MCP surface exposing `sm_search_witnessed`
- Provenance-framed Hermes and Claude hooks

Benchmark tasks must not reinstall, reconfigure, or restart services unless final activation is explicitly required.

## Official STALE pin

- Repository commit: `ea7d391103a151927cd29d2f01d87597a782bdcb`
- Dataset: `.bench-data/stale/T1_T2_400_FULL.json`
- SHA-256: `5f3ec375179e20e2e94469e018189188f34e2e7e5f21cbecbd99fcfa648c1876`
- License: CC-BY-4.0
- 400 cases / 20,000 sessions / three probes per case
- Calibration rows: 0–99
- Held-out rows: 100–399

## Non-negotiable claim boundaries

- Hand-authored compatibility fixtures are not official benchmark results.
- Model-graded metrics are `not_tested` when provider inference is not run.
- Named competitors count only when identical inputs and reproducible adapters run.
- Missing datasets/evaluators are reported as exact blockers, never synthetic passes.
- Preserve dirty work, existing receipts, and source pins. No commits unless explicitly requested.
