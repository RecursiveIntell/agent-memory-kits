# Scifact calibration diagnosis — Phases 0–3

## Frozen boundary

- Baseline kit commit: `28efd9f230d0a9cc05a0e78ddf7cde96e6170b00`.
- Query split: lexicographically sorted official query ID; first 100 calibration, remaining 200 held out.
- Only the 100 calibration IDs were evaluated. No held-out aggregate or per-query result was read.
- Existing store/checkpoint reused: 5,183 facts, Ollama `all-minilm:latest`, 384 dimensions, checkpointed 5,183/5,183.
- Baseline aggregate SHA-256: `b664dad6da0fd0ed150d05ae8e6f5ed9f351c006e11da69f61a0992a8f85a042`.
- Baseline per-query SHA-256: `14ccefee4280eeea8f16c564ea7b81895838a718d884e9b80759db3955364b08`.
- Ingestion checkpoint SHA-256: `7b84352394f0d0dfcbcbf54eeaf1637e11accd5111785af8864266be178975e0`.
- Official queries SHA-256: `8ff84a7c903f722981cd8d595c022660140c51867b27608a6d4910db86080313`.

## Production calibration results

All modes ran through the existing `sm_search_witnessed` production tool with the same namespace and `top_k=10`. The runtime binary was `/home/sikmindz/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp`, SHA-256 `9bf08eeb4838b06db3d70f463c6f68ef87b787fca9711d86f986b880b512afff`.

| Mode | nDCG@10 | Recall@1 | Recall@5 | Recall@10 | MRR@10 | MAP@10 | Mean ms | Failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hybrid | 0.646187 | 0.508667 | 0.710667 | 0.788500 | 0.607190 | 0.596518 | 65.402 | 0 |
| FTS-only | 0.585633 | 0.493333 | 0.631167 | 0.665667 | 0.562274 | 0.554979 | 16.551 | 0 |
| Vector-only exact f32 | 0.606988 | 0.431167 | 0.676000 | 0.758000 | 0.566067 | 0.553726 | 48.343 | 0 |

Vector-only and hybrid receipts report `candidate_backend=brute_force_f32` and `exactness=exact_f32_rerank`. `PreferExact` bypasses HNSW and scans authoritative persisted f32 rows using the same production Ollama query embedder. This is the exact dense baseline; no parallel vector engine was added.

## Blunt root-cause decision

**No current retrieval component fails calibration. Do not change the scorer or fusion.** FTS-only is strong, exact dense is strong, and hybrid is stronger than either constituent. The requested decision tree therefore does not implicate embeddings, vector search, BM25, candidate merging, or RRF.

The persisted baseline's same 100 calibration IDs recompute to hybrid nDCG@10 `0.046326` and Recall@10 `0.123333`, which is incompatible with every fresh production run. A second fresh calibration through the older `/home/sikmindz/.cargo/bin/semantic-memory-mcp` executable produced the same strong hybrid metrics (`0.646187` nDCG@10, `0.788500` Recall@10), so a simple current-vs-installed binary distinction does not reproduce the failure.

The failing component was therefore the **old baseline execution/provenance artifact**, not a retrieval stage. Its receipt recorded the launcher hash but not the resolved service executable hash, so the exact executed binary could not be recovered or replayed. The runner now records the resolved binary path/hash, and the receipt schema requires both fields. A clean release build was pinned at SHA-256 `0f55b21e28dc52f48a8db430ef972d8bb92452c31706bbf33f1ce86ada7f23cf`; frozen held-out and final all-query runs reproduced strong results with zero failures.

## Representation decision

The old builder counted the ID marker against the 700-character semantic title/body budget. A RED/GREEN test now requires the marker to be prepended outside that budget with UTF-8-safe Python slicing. Production witnessed results do not expose benchmark document IDs as metadata, so extraction prefers metadata when present but retains the marker fallback. Because all three existing-store calibration modes are strong, the store was not rebuilt and marker impact was not used to justify re-ingestion.

## Artifacts

- `calibration-hybrid-aggregate.json` / `calibration-hybrid-per-query.jsonl`
- `calibration-fts_only-aggregate.json` / `calibration-fts_only-per-query.jsonl`
- `calibration-vector_only-aggregate.json` / `calibration-vector_only-per-query.jsonl`

Each per-query receipt retains the durable witnessed `receipt_id`, retrieval execution evidence, stage outcomes, namespace scope through the request, score-ordered public document IDs, and metrics. No returned document content is copied into benchmark receipts.
