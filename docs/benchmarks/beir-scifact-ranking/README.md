# BEIR Scifact Retrieval-Ranking Benchmark

This directory contains a valid ordinary retrieval-ranking measurement for semantic-memory. The dataset is the official BEIR Scifact corpus and test qrels: 5,183 corpus documents, 300 judged test queries, and 339 positive qrels. Relevance is public and directly inferable from `qrels/test.tsv`.

## Method

`shared/scripts/benchmark-beir-scifact-ranking.py` downloads and hashes the official archive, then starts one isolated semantic-memory service and persistent store through `shared/scripts/run-server.sh`. Every document is admitted through the production `sm_add_fact` MCP API in one namespace. Document content is capped at 700 characters, following the existing Scifact Ollama tooling's validated boundary, and begins with a stable `[beir-scifact-doc-id:<corpus-id>]` marker. Queries use the production `sm_search_witnessed` MCP API at top 10. Marker extraction preserves returned score order.

The embedder is probed before ingestion and is kept identical for writes and queries. The recorded run uses local Ollama `all-minilm:latest` at 384 dimensions. Successful writes are fsync-checkpointed under the untracked `.bench-data/beir-scifact-ranking/` directory so an interrupted run resumes against the same persistent store.

Metrics are macro-averaged over all selected qrel queries: nDCG@10, Recall@1/5/10, MRR@10, MAP@10, and Success@1/5/10. Aggregate receipts also include query count, positive-qrel count, failures, and retrieval latency p50/p95/mean. Queries with retrieval failures remain in the denominator with zero ranking metrics.

The live production MCP surface does not expose mode-selecting FTS-only or vector-only search calls, so only hybrid is measured. The unavailable modes are explicit in every receipt and are not inferred from hybrid results.

## Reproduction

Technical smoke:

```bash
python3 shared/scripts/benchmark-beir-scifact-ranking.py --smoke --work-dir .bench-data/beir-scifact-ranking --output-dir docs/benchmarks/beir-scifact-ranking --model all-minilm:latest --dimensions 384 --max-chars 700
```

Full official run:

```bash
python3 shared/scripts/benchmark-beir-scifact-ranking.py --work-dir .bench-data/beir-scifact-ranking --output-dir docs/benchmarks/beir-scifact-ranking --model all-minilm:latest --dimensions 384 --max-chars 700
```

The aggregate JSON records the dataset hashes, repository commits and dirty state, exact command/configuration, model, dimensions, production tool names, service statistics, store/checkpoint paths, and per-query artifact hash. `report.md` contains the full-run result; `smoke-report.md` is only the bounded technical gate.

## Claim boundary

This benchmark measures semantic-memory ordinary retrieval ranking on public Scifact qrels. It makes no competitor comparison or superiority claim and uses no hidden labels, synthetic query-copy distractors, or test-qrel tuning.
