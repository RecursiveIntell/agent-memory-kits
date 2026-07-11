# Semantic-Memory BEIR Scifact Retrieval Ranking

- Status: **measured**
- Run kind: `full`
- Corpus documents: 5,183
- Official test queries: 300
- Positive qrels: 339
- Embedder: Ollama `all-minilm:latest`, 384 dimensions
- Production path: `sm_add_fact` -> `sm_search_witnessed`

## Hybrid results

| nDCG@10 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | MAP@10 | Success@1 | Success@5 | Success@10 | Failures |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.054714 | 0.010000 | 0.038333 | 0.136111 | 0.032115 | 0.030592 | 0.010000 | 0.040000 | 0.146667 | 0 |

Latency: p50 `60.561 ms`, p95 `69.624 ms`, mean `60.695 ms`.

## Mode boundary

- FTS-only: **not_exposed** — production MCP tool list exposes no mode-selecting FTS-only/vector-only retrieval API
- Vector-only: **not_exposed** — production MCP tool list exposes no mode-selecting FTS-only/vector-only retrieval API
- Hybrid results are not presented as either unavailable mode.

## Provenance and artifacts

- Corpus SHA-256: `sha256:dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6`
- Test qrels SHA-256: `sha256:0864bb985e0ca2367ba217977e72004d549054b2b06666ed9d4825ac7c21284c`
- Per-query JSONL: `/home/sikmindz/Coding/agent-memory-kits/docs/benchmarks/beir-scifact-ranking/per-query.jsonl` (`sha256:14ccefee4280eeea8f16c564ea7b81895838a718d884e9b80759db3955364b08`)
- Store: `/home/sikmindz/Coding/agent-memory-kits/.bench-data/beir-scifact-ranking/store-full-all-minilm-latest-700`
- Ingestion checkpoint: `/home/sikmindz/Coding/agent-memory-kits/.bench-data/beir-scifact-ranking/ingestion-full-all-minilm-latest-700.jsonl`

## Exact command

```bash
python3 shared/scripts/benchmark-beir-scifact-ranking.py --work-dir .bench-data/beir-scifact-ranking --output-dir docs/benchmarks/beir-scifact-ranking --model all-minilm:latest --dimensions 384 --max-chars 700
```

## Claim boundary

These are ordinary retrieval-ranking measurements on public BEIR Scifact test qrels. No competitor comparison, superiority claim, hidden-label feature, query-copy distractor, or test-qrel tuning is included.
