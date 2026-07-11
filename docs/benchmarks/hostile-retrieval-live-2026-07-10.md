# Live Retrieval Gate — 2026-07-10

## Result

PASS on the narrow live retrieval gate: 10/10 expected facts were returned at rank 1 from a 50-fact namespace.

- recall@5: 1.0000
- nDCG@5: 1.0000
- MRR: 1.0000
- server: real `semantic-memory-mcp` HTTP process
- embedder: mock
- corpus: 10 uniquely identifiable operational facts plus 40 distractors

## Receipt

`hostile-retrieval-live-2026-07-10.json`

## Commands

```text
cargo run --quiet -- --memory-dir /tmp/sm-hostile-live --embedder mock --http-port 1741 --http-only
SEMANTIC_MEMORY_HTTP_PORT=1741 python shared/scripts/benchmark-recall.py --fixtures-dir /tmp/sm-hostile-retrieval-fixtures --top-k 5 --out docs/benchmarks/hostile-retrieval-live-2026-07-10.json
python -m pytest -q
```

## Harness defect found and fixed

The HTTP endpoint emits `result_id: fact:<uuid>`, while the recall harness ignored `result_id` and fixtures stored bare UUIDs. That produced a false 0.0 score even when the correct fact was rank 1. Tests were added first, observed failing, then the extractor and ID normalization were fixed.

## Claim boundary

This proves the HTTP retrieval path and benchmark receipt machinery work on a small lexical fixture. It does not prove best-in-class semantic retrieval, production scale, model-embedding quality, contradiction handling, temporal correctness, or superiority over Mem0, Letta, or Graphiti. Those require the separate hostile integrity benchmark and named-system adapters.
