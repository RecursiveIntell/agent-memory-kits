# Named Competitor Deterministic Adapters

All measured rows use the pinned official STALE M_old → M_new sequence and the same three probes. Sleeper is evaluated only for a native write-admission/governance claim.

## Results

| Competitor | Pin | STALE rows | Current | Stale suppression | Conflict | History | Mean latency ms | Sleeper |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `mem0` | `2.0.11` / `c9af55986e4a` | not tested | — | — | — | — | — | `not_supported` |
| `graphiti_zep` | `0.29.2` / `526dcad7a300` | not tested | — | — | — | — | — | `not_supported` |
| `letta` | `0.16.8` / `b76da9092518` | not tested | — | — | — | — | — | `not_supported` |
| `langmem` | `0.0.30` / `c01e273b94aa` | not tested | — | — | — | — | — | `not_supported` |

## Blockers and boundaries

- `mem0` — The previously pinned isolated interpreter /tmp/agent-memory-kits-competitors-20260711/mem0-venv/bin/python is absent. No replacement environment was installed because this benchmark permits no paid inference or environment mutation.
- `graphiti_zep` — no isolated competitor interpreter or blocker receipt was supplied
- `letta` — no isolated competitor interpreter or blocker receipt was supplied
- `langmem` — The previously pinned isolated interpreter /tmp/agent-memory-kits-competitors-20260711/langmem-venv/bin/python is absent. No replacement environment was installed because this benchmark permits no paid inference or environment mutation.

- Mem0 history is a native update-event log, not bitemporal as-of search.
- Letta's pinned legacy V1 server is maintenance-mode. Its embedding-optional passage API documents insert/list/search/delete but no passage update or history path; those capabilities are unavailable and are not adapter-emulated.
- Letta agent creation structurally requires an LLM model handle, but direct passage operations do not invoke that model.
- LangMem native keyed update overwrites the old item; history/conflict preservation are unavailable, not adapter-emulated.
- Each case uses an isolated namespace containing one keyed current memory after native update. The probes therefore measure update/search visibility and state semantics, not multi-candidate retrieval ranking.
- Both measured adapters receive the same fixed SHA-256-derived 16-dimensional local embedding through their supported public embedding interfaces; no embedding provider call is made.
- `not_supported` Sleeper cells are not failures. None of the measured competitors documents a write-admission/governance gate on these public APIs.
- These are deterministic state/evidence proxies, not official model-graded response scores or a general superiority claim.

## Exact command

```bash
python3 shared/scripts/benchmark-diagnostic-memory.py --official-stale-dataset .bench-data/stale/T1_T2_400_FULL.json --official-stale-ranking --official-stale-launch-local --official-stale-cases-out docs/benchmarks/ranking-official/per-case.jsonl --markdown-out docs/benchmarks/ranking-official/report.md --competitor-cases-dir docs/benchmarks/ranking-official/competitors --competitor-report-out docs/benchmarks/ranking-official/competitor-report.md --competitor-blockers docs/benchmarks/ranking-official/competitor-blockers.json --out docs/benchmarks/ranking-official/aggregate.json
```
