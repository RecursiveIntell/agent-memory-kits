# Named Competitor Deterministic Adapters

All measured rows use the pinned official STALE M_old → M_new sequence and the same three probes. Sleeper is evaluated only for a native write-admission/governance claim.

## Results

| Competitor | Pin | STALE rows | Current | Stale suppression | Conflict | History | Mean latency ms | Sleeper |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `mem0` | `2.0.11` / `c9af55986e4a` | not tested | — | — | — | — | — | `not_supported` |
| `graphiti_zep` | `0.29.2` / `526dcad7a300` | not tested | — | — | — | — | — | `not_supported` |
| `letta` | `0.16.8` / `b76da9092518` | 400 | 0.000 | 1.000 | 0.000 | 0.000 | 5679.516133 | `not_supported` |
| `langmem` | `0.0.30` / `c01e273b94aa` | not tested | — | — | — | — | — | `not_supported` |

## Blockers and boundaries

- `mem0` — no isolated competitor interpreter or blocker receipt was supplied
- `graphiti_zep` — graphiti-core 0.29.2 installed with its kuzu extra and reached the public Graphiti.add_episode API using the documented local Ollama OpenAI-compatible clients, but no row completed: an explicit group_id first raised AttributeError because KuzuDriver lacked _database; the documented default-group retry then failed inside add_episode with Kuzu RuntimeError because RelatesToNode_ lacked the edge_name_and_fact FTS index. No result was simulated.
- `langmem` — no isolated competitor interpreter or blocker receipt was supplied

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
python /home/sikmindz/.cache/semantic-memory-bench/letta-final/benchmark-runner.py --official-stale-dataset /home/sikmindz/Coding/agent-memory-kits/.bench-data/stale/T1_T2_400_FULL.json --competitor-python letta=/home/sikmindz/.cache/semantic-memory-bench/competitors/letta-venv/bin/python --competitor-all-stale --four-batches-of-100 --out /home/sikmindz/.cache/semantic-memory-bench/letta-final/output/final-aggregate.json
```
