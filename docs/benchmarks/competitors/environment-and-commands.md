# Competitor Environment And Commands

## Host and isolation

- Host: `Linux 7.0.9-200.nobara.fc43.x86_64 x86_64 GNU/Linux`
- Repository commit at execution: `81d90706c4c3cecb77f4094179d466500e7082d8` (dirty worktree preserved; no commit made)
- Isolated interpreter: `/usr/bin/python3.11`, Python `3.11.15`
- Installer: `uv 0.9.27 (Homebrew 2026-01-26)`
- Git: `2.54.0`
- Local Graphiti smoke provider: existing Ollama `0.30.8`; no model pull, restart, configuration change, or hosted request
- LLM/judge calls in measured Mem0 and LangMem rows: `0`
- Letta checkout/interpreter: `/home/sikmindz/.cache/semantic-memory-bench/competitors/letta` and `/home/sikmindz/.cache/semantic-memory-bench/competitors/letta-venv/bin/python`
- Letta isolation: a free loopback port plus temporary `HOME`, `LETTA_DIR`, config, and SQLite database; active semantic-memory services and user config were untouched
- Letta maintenance boundary: this pin is the legacy V1 server in maintenance mode; active development has moved to Letta Agent

## Upstream pins

| Candidate | Package | Version | Commit | License | LICENSE SHA-256 | Manifest SHA-256 |
|---|---|---|---|---|---|---|
| Mem0 | `mem0ai` | `2.0.11` | `c9af55986e4a31aa98931b6b909d5639e9b2013a` | Apache-2.0 | `0bbcbe931c353293a2fafce08326181dfeea0e568c566afd4ce8337a70f5e219` | `faebb337990d1c0cfe83494e59ffa419fdf47c0690ebcc259470d6dc4aba0186` |
| Graphiti / Zep | `graphiti-core` | `0.29.2` | `526dcad7a300f3c5c506ff96a68bcdc7ca9f97ed` | Apache-2.0 | `2825300b20d7b951209835a4a331f29e24725a39d65168e4b831df53aa372650` | `e8157e9b9c84a01b86e4e02e6cdc586b6e42e61d3c1612d1bb5aeef2f8309b44` |
| Letta | `letta` | `0.16.8` | `b76da9092518cbaa2d09042e52fdcbde69243e18` | Apache-2.0 | `984c6db99fc6609803108dfc196762118662cd94b82a456dd9217583f18f3612` | `ba86147a334a4900962b260d1912e263e011e8698377327b9f1a8fd943540c3e` |
| LangMem | `langmem` | `0.0.30` | `c01e273b94aa4c06e41d0ed1ccce0db17de2bc11` | MIT | `98af1351ea856e008c835bc89a312905960a318072f950732bf346c741027c7d` | `6a964d268d23b8860c848b7b23f2dc6998204eaa0eb28cfe2d404359eb51611a` |

The manifest hash is the pinned checkout's root `pyproject.toml` SHA-256.

## Clone commands

```bash
git clone --depth 1 --filter=blob:none https://github.com/mem0ai/mem0.git /tmp/agent-memory-kits-competitors-20260711/mem0
git clone --depth 1 --filter=blob:none https://github.com/getzep/graphiti.git /tmp/agent-memory-kits-competitors-20260711/graphiti
git clone --depth 1 --filter=blob:none https://github.com/letta-ai/letta.git /tmp/agent-memory-kits-competitors-20260711/letta
git clone --depth 1 --filter=blob:none https://github.com/langchain-ai/langmem.git /tmp/agent-memory-kits-competitors-20260711/langmem
```

## Installation commands

```bash
uv venv --python /usr/bin/python3.11 /tmp/agent-memory-kits-competitors-20260711/mem0-venv
uv pip install --python /tmp/agent-memory-kits-competitors-20260711/mem0-venv/bin/python /tmp/agent-memory-kits-competitors-20260711/mem0 'langchain>=0.3.30,<1.0.0'

uv venv --python /usr/bin/python3.11 /tmp/agent-memory-kits-competitors-20260711/graphiti-venv
uv pip install --python /tmp/agent-memory-kits-competitors-20260711/graphiti-venv/bin/python '/tmp/agent-memory-kits-competitors-20260711/graphiti[kuzu]'

# Letta installation was supplied complete for this run:
/home/sikmindz/.cache/semantic-memory-bench/competitors/letta-venv/bin/python -c 'import importlib.metadata; print(importlib.metadata.version("letta"))'

uv venv --python /usr/bin/python3.11 /tmp/agent-memory-kits-competitors-20260711/langmem-venv
uv pip install --python /tmp/agent-memory-kits-competitors-20260711/langmem-venv/bin/python /tmp/agent-memory-kits-competitors-20260711/langmem
```

Graphiti installed and failed at its public runtime path. The old Letta disk-space blocker is obsolete: the checkout measured `54M`, the environment `772M`, and the home filesystem had `208G` free. The completed Letta environment instead failed at server import after both bounded startup strategies because `asyncpg` is absent from the environment lock. Exact blockers are in `blockers.json`.

## Measured environment locks

```bash
uv pip freeze --python /tmp/agent-memory-kits-competitors-20260711/mem0-venv/bin/python > docs/benchmarks/competitors/locks/mem0.lock.txt
uv pip freeze --python /tmp/agent-memory-kits-competitors-20260711/langmem-venv/bin/python > docs/benchmarks/competitors/locks/langmem.lock.txt
uv pip freeze --python /home/sikmindz/.cache/semantic-memory-bench/competitors/letta-venv/bin/python > docs/benchmarks/competitors/locks/letta.lock.txt
```

- `mem0.lock.txt`: SHA-256 `66bd381cd062a4e913ce0cb002261d426df112fbb79cf6373b51308e0a6c3ffd`
- `langmem.lock.txt`: SHA-256 `23a0042c5a67e0903042e6eb7ab7a2b56af183d837a818a8f5db293da3e78932`
- `letta.lock.txt`: SHA-256 `e3d6f9930a2dac14190a890b266999914e207024bca6d3c537e1781fd4ede0f8`

## Letta bounded smoke command

```bash
python shared/scripts/benchmark-diagnostic-memory.py --official-stale-dataset .bench-data/stale/T1_T2_400_FULL.json --competitor-python letta=/home/sikmindz/.cache/semantic-memory-bench/competitors/letta-venv/bin/python --competitor-cases-dir /tmp/letta-smoke-cases --competitor-report-out /tmp/letta-smoke-report.md --competitor-blockers docs/benchmarks/competitors/blockers.json --out /tmp/letta-smoke-receipt.json
```

The selected rows were the predeclared calibration indices 0–9 and held-out indices 100–109. Both server strategies failed before health readiness with `ModuleNotFoundError: No module named 'asyncpg'`; zero rows executed, so the Letta all-400 command was intentionally not run.

## Final all-row command

```bash
python3 shared/scripts/benchmark-diagnostic-memory.py --official-stale-dataset .bench-data/stale/T1_T2_400_FULL.json --competitor-python mem0=/tmp/agent-memory-kits-competitors-20260711/mem0-venv/bin/python --competitor-python langmem=/tmp/agent-memory-kits-competitors-20260711/langmem-venv/bin/python --competitor-all-stale --competitor-cases-dir docs/benchmarks/competitors --competitor-locks-dir docs/benchmarks/competitors/locks --competitor-report-out docs/benchmarks/competitors/report.md --competitor-blockers docs/benchmarks/competitors/blockers.json --out docs/benchmarks/competitors/aggregate-receipt.json
```

The predeclared Mem0/LangMem 20-row smoke used the same command without `--competitor-all-stale` and wrote only to `/tmp`. It completed in 8.2 seconds with zero measured-row runtime failures, permitting those adapters' predeclared all-400 promotion. That promotion statement does not apply to Letta.

## Letta final bounded retry

- Isolated environment: `/home/sikmindz/.cache/semantic-memory-bench/competitors/letta-venv`
- Installation succeeded after adding `asyncpg`.
- Both documented startup strategies reached application lifespan but attempted PostgreSQL on localhost:5432 despite SQLite settings.
- Rows measured: 0; no PostgreSQL service was provisioned; no result simulated.
