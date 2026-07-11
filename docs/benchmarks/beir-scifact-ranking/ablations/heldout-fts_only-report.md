# Semantic-Memory BEIR Scifact Retrieval Ranking

- Status: **measured**
- Run kind: `full`
- Corpus documents: 5,183
- Official test queries: 200
- Positive qrels: 226
- Embedder: Ollama `all-minilm:latest`, 384 dimensions
- Production path: `sm_add_fact` -> `sm_search_witnessed`

## fts_only results

| nDCG@10 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | MAP@10 | Success@1 | Success@5 | Success@10 | Failures |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.634805 | 0.484167 | 0.713917 | 0.768917 | 0.598929 | 0.585847 | 0.505000 | 0.735000 | 0.790000 | 0 |

Latency: p50 `17.707 ms`, p95 `21.923 ms`, mean `17.627 ms`.

## Mode boundary

- hybrid: **not_selected** — not selected for this mode-separated run
- fts_only: **measured**
- vector_only: **not_selected** — not selected for this mode-separated run

## Provenance and artifacts

- Corpus SHA-256: `sha256:dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6`
- Test qrels SHA-256: `sha256:0864bb985e0ca2367ba217977e72004d549054b2b06666ed9d4825ac7c21284c`
- Per-query JSONL: `/home/sikmindz/Coding/agent-memory-kits/docs/benchmarks/beir-scifact-ranking/ablations/heldout-fts_only-per-query.jsonl` (`sha256:4535d8a80fb019e58edfb9fea590c477ac43b5e003b2e1e7f58281288fedfab2`)
- Store: `/home/sikmindz/Coding/agent-memory-kits/.bench-data/beir-scifact-ranking/store-full-all-minilm-latest-700`
- Ingestion checkpoint: `/home/sikmindz/Coding/agent-memory-kits/.bench-data/beir-scifact-ranking/ingestion-full-all-minilm-latest-700.jsonl`

## Exact command

```bash
python3 shared/scripts/benchmark-beir-scifact-ranking.py --work-dir .bench-data/beir-scifact-ranking --output-dir docs/benchmarks/beir-scifact-ranking/ablations --model all-minilm:latest --dimensions 384 --max-chars 700 --mode fts_only --query-split heldout
```

## Claim boundary

These are ordinary retrieval-ranking measurements on public BEIR Scifact test qrels. No competitor comparison, superiority claim, hidden-label feature, query-copy distractor, or test-qrel tuning is included.
