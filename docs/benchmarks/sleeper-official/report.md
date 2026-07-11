# Official Sleeper Deterministic Admission / Action-Gate Adapter

- Official repository: `/tmp/sleeper-official` at `1eb8b7e33b505299155baf3be776545b1620f022`
- Rows: `520`; slices `{"agent_action": 100, "behavior": 250, "benign_save": 70, "non_english": 100}`
- Per-case sidecar: `docs/benchmarks/sleeper-official/per-case.jsonl` (`sha256:eb9b8b7b8203660a2cea895c94d1b93f3513760d3356033f76a6c44d59d98969`)
- LLM calls: `0`; judge calls: `0`
- Upstream licensing caveat: Code, prompts, adversarial goals, and benchmark annotations are released by Sleeper; bundled evaluation data may derive from third-party corpora whose licenses or terms continue to govern source-derived portions.

## Exact upstream files

| Slice | Source SHA-256 | Generated / evaluated split SHA-256 | Rows |
|---|---|---|---:|
| `behavior` | `sha256:9e56165e71eba5fc3090e7b253784826fffc09635d6e6637cd031e6e2ee9e68b` | `sha256:3f1ac72166e29dbcd03b38f32169cfb3b3643c7d5aed043001f677ac8b043c7d` | 250 |
| `agent_action` | `sha256:c05b4e725e6952ea881b4bc9253bab0424ad4f3feeb5d4174b5f63bb3a353b3b` | `sha256:119fc9065ab40a313a36fa4cdedbe2e5ce58a472153a3c7a280bdb89dd820a3e` | 100 |
| `non_english` | `sha256:16ce9962fe34f2ed888849a5af67d2cfdb4ebb3a898da2d413406b319191097c` | `sha256:20b1ec2bd5054711b596318711576097e8a3d4c6df443fc83e6644d18c48cb66` | 100 |
| `benign_save` | `sha256:9d3dfa5b6f5a7d92edf837e572d67a3fa9284a27f4fa06ac5b37fe8cce88b04c` | `sha256:9d3dfa5b6f5a7d92edf837e572d67a3fa9284a27f4fa06ac5b37fe8cce88b04c` | 70 |

## Predeclared baseline cells

- `ungoverned_append_only` — deterministic append-only control that admits each candidate without provenance, authority, or action gating
- `mutable_latest` — deterministic mutable-latest control that admits each candidate without provenance, authority, or action gating
- `governed_semantic_memory` — actual isolated semantic-memory MCP admission and witnessed retrieval; no MCP behavior is simulated
- `no_memory` — deterministic no-write control with no stored candidate

## Aggregate deterministic results

| Cell | Admission outcomes | Poison retrieval containment | Benign-save retention | Mean latency ms | Failures |
|---|---|---:|---:|---:|---:|
| `ungoverned_append_only` | `{"accept": 520}` | 0.0 | 1.0 | 0.0 | 0 |
| `mutable_latest` | `{"accept": 520}` | 0.0 | 1.0 | 0.0 | 0 |
| `governed_semantic_memory` | `{"accept": 70, "reject": 450}` | 1.0 | 1.0 | 0.854345 | 0 |
| `no_memory` | `{"no_write": 520}` | 1.0 | 0.0 | 0.0 | 0 |

## Authority and metric boundaries

- The governed cell calls the actual isolated MCP `sm_add_fact` admission gate and `sm_search_witnessed`; official source text is represented only by row/content digests in artifacts, not copied into this repository.
- The MCP append contract frames evidence-backed sources as external evidence with denied assertion and action scopes. Purpose-specific governed assertion/action access and multi-principal decisions are not exposed by this MCP tool surface, so those containment metrics are `not_tested`, not inferred from a policy simulation.
- `not_tested`: official Sleeper response-quality, attack-success, semantic-score, and model-graded metrics require subject/manager/judge provider inference; this deterministic adapter made no provider or judge calls.
- No response-quality, official paper score, competitor score, or model-quality claim is made.

## Exact command

```bash
python3 shared/scripts/benchmark-diagnostic-memory.py --official-sleeper-root /tmp/sleeper-official --official-sleeper-launch-local --official-sleeper-cases-out docs/benchmarks/sleeper-official/per-case.jsonl --markdown-out docs/benchmarks/sleeper-official/report.md --out docs/benchmarks/sleeper-official/aggregate-receipt.json
```
