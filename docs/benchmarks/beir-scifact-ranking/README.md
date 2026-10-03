# BEIR Scifact Retrieval-Ranking Benchmark

This directory contains source-bound artifacts from recorded ordinary retrieval-ranking runs for semantic-memory. The dataset is the official BEIR Scifact corpus and test qrels: 5,183 corpus documents, 300 judged test queries, and 339 positive qrels. Relevance is public and directly inferable from `qrels/test.tsv`.

## Method

`shared/scripts/benchmark-beir-scifact-ranking.py` downloads and hashes the official archive, then starts one isolated semantic-memory service and persistent store through `shared/scripts/run-server.sh`. Every document is admitted through the production `sm_add_fact` MCP API in one namespace. Document content is capped at 700 characters, following the existing Scifact Ollama tooling's validated boundary, and begins with a stable `[beir-scifact-doc-id:<corpus-id>]` marker. Queries use the production `sm_search_witnessed` MCP API at top 10. Marker extraction preserves returned score order.

The embedder is probed before ingestion and is kept identical for writes and queries. The recorded run uses local Ollama `all-minilm:latest` at 384 dimensions. Successful writes are fsync-checkpointed under the untracked `.bench-data/beir-scifact-ranking/` directory so an interrupted run resumes against the same persistent store.

Metrics are macro-averaged over all selected qrel queries: nDCG@10, Recall@1/5/10, MRR@10, MAP@10, and Success@1/5/10. Aggregate receipts also include query count, positive-qrel count, failures, and retrieval latency p50/p95/mean. Queries with retrieval failures remain in the denominator with zero ranking metrics.

The current harness selects `hybrid`, `fts_only` or `vector_only` with `--mode` and passes that selection as `retrieval_mode` to `sm_search_witnessed`.  Each invocation measures one selected mode; other modes are recorded as `not_selected`, not unavailable.  The checked-in [final-modes artifacts](final-modes/) include separate all-query receipts for all three modes.  These are recorded results from their identified native binary and source snapshot, not a fresh certification of the currently installed server.

## Reproduction

Run from the agent-memory-kits repository root with a compatible, explicitly selected native server and local Ollama model.  The harness requests the `full` profile and an authenticated warm HTTP sidecar; the selected server must admit its governed public-document capture requests.  Configure the private HTTP and operator-authority token files through the [canonical launcher settings](../../CURRENT_STACK.md#configuration-that-reaches-the-native-server).  Do not bypass transport or write-admission gates to reproduce an older receipt.  Preserve the selected binary, source identity and configuration with the new artifacts.

Technical smoke:

```bash
python3 shared/scripts/benchmark-beir-scifact-ranking.py --smoke --work-dir .bench-data/beir-scifact-ranking --output-dir docs/benchmarks/beir-scifact-ranking --model all-minilm:latest --dimensions 384 --max-chars 700 --mode hybrid --query-split all
```

Mode-separated all-query runs after calibration and held-out evaluation:

```bash
for mode in fts_only vector_only hybrid; do
  python3 shared/scripts/benchmark-beir-scifact-ranking.py \
    --work-dir .bench-data/beir-scifact-ranking \
    --output-dir docs/benchmarks/beir-scifact-ranking/final-modes \
    --model all-minilm:latest --dimensions 384 --max-chars 700 \
    --mode "$mode" --query-split all
done
```

For configuration selection, use `--query-split calibration`, freeze the configuration, then use `--query-split heldout`.  Do not tune on held-out or all-query outcomes.

The aggregate JSON records the dataset hashes, repository commits and dirty state, exact command/configuration, model, dimensions, production tool names, service statistics, store/checkpoint paths, and per-query artifact hash. Current full-run output uses `<split>-<mode>-{per-query.jsonl,aggregate.json,report.md}`; smoke output uses `smoke-{per-query.jsonl,aggregate.json,report.md}`.  The older `report.md` and `aggregate.json` remain historical hybrid artifacts.  Keep raw per-query rows and the matching aggregate together, and inspect their executable/configuration identity before quoting metrics.  `smoke-report.md` is only a bounded technical gate.

## Claim boundary

This benchmark measures semantic-memory ordinary retrieval ranking on public Scifact qrels. It makes no competitor comparison or superiority claim and uses no hidden labels, synthetic query-copy distractors, or test-qrel tuning.

