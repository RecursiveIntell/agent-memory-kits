# Named Competitor Deterministic Adapters

All measured rows use the pinned official STALE M_old → M_new sequence and the same three probes. Sleeper is evaluated only for a native write-admission/governance claim.

## Results

| Competitor | Pin | STALE rows | Current | Stale suppression | Conflict | History | Mean latency ms | Sleeper |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `mem0` | `2.0.11` / `c9af55986e4a` | 400 | 0.117 | 1.000 | 1.000 | 1.000 | 6.493999 | `not_supported` |
| `graphiti_zep` | `0.29.2` / `526dcad7a300` | not tested | — | — | — | — | — | `not_supported` |
| `letta` | `0.16.8` / `b76da9092518` | not tested | — | — | — | — | — | `not_supported` |
| `langmem` | `0.0.30` / `c01e273b94aa` | 400 | 1.000 | 1.000 | 0.000 | 0.000 | 8.301296 | `not_supported` |

## Blockers and boundaries

- `graphiti_zep` — graphiti-core 0.29.2 installed with its kuzu extra and reached the public Graphiti.add_episode API using the documented local Ollama OpenAI-compatible clients, but no row completed: an explicit group_id first raised AttributeError because KuzuDriver lacked _database; the documented default-group retry then failed inside add_episode with Kuzu RuntimeError because RelatesToNode_ lacked the edge_name_and_fact FTS index. No result was simulated.
- `letta` — Letta 0.16.8 installed successfully in an isolated 241-package environment after moving off the constrained /tmp filesystem and adding its undeclared asyncpg runtime dependency. A 20-row smoke still executed zero rows: both the public `letta server` CLI and documented `start_server` path reached application startup, but the maintenance-mode V1 server lifespan initialized an async PostgreSQL engine and attempted localhost:5432 even though isolated settings reported DatabaseChoice.SQLITE and the sqlite extra was installed. The final scrubbed direct startup failed with asyncpg connection refused on ::1/127.0.0.1:5432. No PostgreSQL service was provisioned, no public memory row completed, and no result was simulated.

- Mem0 history is a native update-event log, not bitemporal as-of search.
- Letta's pinned legacy V1 server is maintenance-mode. Its embedding-optional passage API documents insert/list/search/delete but no passage update or history path; those capabilities are unavailable and are not adapter-emulated.
- Letta agent creation structurally requires an LLM model handle, but direct passage operations do not invoke that model.
- LangMem native keyed update overwrites the old item; history/conflict preservation are unavailable, not adapter-emulated.
- Each case uses an isolated namespace containing one keyed current memory after native update. The probes therefore measure update/search visibility and state semantics, not multi-candidate retrieval ranking.
- Both measured adapters receive the same fixed SHA-256-derived 16-dimensional local embedding through their supported public embedding interfaces; no embedding provider call is made.
- `not_supported` Sleeper cells are not failures. None of the measured competitors documents a write-admission/governance gate on these public APIs.
- These are deterministic state/evidence proxies, not official model-graded response scores or a general superiority claim.

## Exact commands

The prior successful Mem0/LangMem all-row command remains recorded below. Letta was attempted only with the required 20-row smoke command; because it executed zero rows, `--competitor-all-stale` was not run for Letta.

```bash
python3 shared/scripts/benchmark-diagnostic-memory.py --official-stale-dataset .bench-data/stale/T1_T2_400_FULL.json --competitor-python mem0=/tmp/agent-memory-kits-competitors-20260711/mem0-venv/bin/python --competitor-python langmem=/tmp/agent-memory-kits-competitors-20260711/langmem-venv/bin/python --competitor-all-stale --competitor-cases-dir docs/benchmarks/competitors --competitor-locks-dir docs/benchmarks/competitors/locks --competitor-report-out docs/benchmarks/competitors/report.md --competitor-blockers docs/benchmarks/competitors/blockers.json --out docs/benchmarks/competitors/aggregate-receipt.json

python shared/scripts/benchmark-diagnostic-memory.py --official-stale-dataset .bench-data/stale/T1_T2_400_FULL.json --competitor-python letta=/home/sikmindz/.cache/semantic-memory-bench/competitors/letta-venv/bin/python --competitor-cases-dir /tmp/letta-smoke-cases --competitor-report-out /tmp/letta-smoke-report.md --competitor-blockers docs/benchmarks/competitors/blockers.json --out /tmp/letta-smoke-receipt.json
```
