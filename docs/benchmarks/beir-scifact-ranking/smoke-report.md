# Semantic-Memory BEIR Scifact Retrieval Ranking

- Status: **measured**
- Run kind: `smoke`
- Corpus documents: 20
- Official test queries: 5
- Positive qrels: 6
- Embedder: Ollama `all-minilm:latest`, 384 dimensions
- Production path: `sm_add_fact` -> `sm_search_witnessed`

## Hybrid results

| nDCG@10 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | MAP@10 | Success@1 | Success@5 | Success@10 | Failures |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.189279 | 0.000000 | 0.200000 | 0.400000 | 0.125000 | 0.125000 | 0.000000 | 0.200000 | 0.400000 | 0 |

Latency: p50 `25.671 ms`, p95 `28.133 ms`, mean `26.204 ms`.

## Mode boundary

- FTS-only: **not_exposed** — production MCP tool list exposes no mode-selecting FTS-only/vector-only retrieval API
- Vector-only: **not_exposed** — production MCP tool list exposes no mode-selecting FTS-only/vector-only retrieval API
- Hybrid results are not presented as either unavailable mode.

## Provenance and artifacts

- Corpus SHA-256: `sha256:dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6`
- Test qrels SHA-256: `sha256:0864bb985e0ca2367ba217977e72004d549054b2b06666ed9d4825ac7c21284c`
- Per-query JSONL: `/home/sikmindz/Coding/agent-memory-kits/docs/benchmarks/beir-scifact-ranking/smoke-per-query.jsonl` (`sha256:c315ede1a9fa64c849cd27f8ef89286976c890a3d1705538a9fd12adc6e31b3e`)
- Store: `/home/sikmindz/Coding/agent-memory-kits/.bench-data/beir-scifact-ranking/store-smoke-all-minilm-latest-700`
- Ingestion checkpoint: `/home/sikmindz/Coding/agent-memory-kits/.bench-data/beir-scifact-ranking/ingestion-smoke-all-minilm-latest-700.jsonl`

## Exact command

```bash
python3 shared/scripts/benchmark-beir-scifact-ranking.py --smoke --work-dir .bench-data/beir-scifact-ranking --output-dir docs/benchmarks/beir-scifact-ranking --model all-minilm:latest --dimensions 384 --max-chars 700
```

## Claim boundary

These are ordinary retrieval-ranking measurements on public BEIR Scifact test qrels. No competitor comparison, superiority claim, hidden-label feature, query-copy distractor, or test-qrel tuning is included.
