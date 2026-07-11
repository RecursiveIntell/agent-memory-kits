# RecursiveIntell Stack-Wide Capability Reuse Map

Generated from live canonical Cargo manifests plus the portfolio audit. Mandatory preflight for any agent modifying semantic-memory, benchmarks, plugins, governance, proof, or operator surfaces.

## Hard rule

Before creating a new contract, crate, ledger, receipt, policy engine, benchmark runner, adapter, operator shell, or persistence layer: search this map and inspect the named canonical implementation. Integrate or extend it unless a controller-verified gap proves reuse impossible.

## Canonical capability groups

### Authoritative Memory And State

- `bitemporal-runtime` — `/home/sikmindz/Coding/Libraries/bitemporal-runtime` — Bitemporal truth primitives — valid_time/recorded_time tracking, append-supersede, as-of queries, temporal snapshots.
- `constitutional-memory` — `/home/sikmindz/Coding/Libraries/constitutional-memory` — Typed charter and archive surface crate with bounded amendment checks; not a hidden governance runtime
- `continuity-runtime` — `/home/sikmindz/Coding/Libraries/continuity-runtime` — Typed continuity and incident surface crate with bounded recovery profiles; not an incident-command runtime
- `knowledge-runtime` — `/home/sikmindz/Coding/Libraries/knowledge-runtime` — Bounded orchestration scaffold for semantic-memory: classification, routing, scoped entity resolution, provenance-preserving merge, and projection status tracking
- `semantic-memory` — `/home/sikmindz/Coding/Libraries/semantic-memory` — Local-first hybrid semantic search (SQLite + FTS5 + usearch 2.25) with bitemporal truth and typed receipts
- `semantic-memory` — `/home/sikmindz/Coding/Libraries/turbo-semantic-archive` — Hybrid semantic search with SQLite, FTS5, and HNSW — built for AI agents
- `semantic-memory-forge` — `/home/sikmindz/Coding/Libraries/semantic-memory-forge` — Forge verification truth: evidence bundles, export envelopes, and causal estimation substrate
- `semantic-memory-mcp` — `/home/sikmindz/Coding/Libraries/semantic-memory-mcp` — MCP server wrapping semantic-memory — local-first knowledge management with evidence-scored retrieval, contradiction detection, and adaptive routing

### Evidence Claims Receipts Identity

- `assurance-runtime` — `/home/sikmindz/Coding/Libraries/assurance-runtime` — Typed deployability and certification surface crate with bounded readiness profiles; not an orchestration runtime
- `attestation-exchange` — `/home/sikmindz/Coding/Libraries/attestation-exchange` — Typed attestation exchange contracts for envelope, trust-root, and transparency artifacts
- `cea-core` — `/home/sikmindz/Coding/Libraries/Primitives/cea-core` — cea-core — RecursiveIntell Forge primitive
- `cea-sqlite` — `/home/sikmindz/Coding/Libraries/Primitives/cea-sqlite` — SQLite implementation of the cea-store contract
- `cea-store` — `/home/sikmindz/Coding/Libraries/Primitives/cea-store` — Storage contract and row types for causal edit attribution graphs
- `claim-ledger` — `/home/sikmindz/Coding/Libraries/claim-ledger` — Deterministic, local-first claim/evidence/provenance ledger. Creates receipts for all material operations.
- `forge-memory-bridge` — `/home/sikmindz/Coding/Libraries/forge-memory-bridge` — Transform Forge export envelopes into projection import batches for semantic-memory
- `receipt-bench` — `/home/sikmindz/Coding/Libraries/receipt-bench` — Replayable benchmark substrate for semantic search, compression, and memory operations
- `stack-ids` — `/home/sikmindz/Coding/Libraries/stack-ids` — Shared identity, scope, trace, and digest primitives for the local-first AI systems stack

### Verification Policy Promotion

- `boundary-compiler` — `/home/sikmindz/Coding/Libraries/boundary-compiler` — RFC 8785 JSON Canonicalization (JCS) with boundary profiles and duplicate-key rejection
- `boundary-compiler-core` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/boundary-compiler-core` — P31 v11A boundary compiler microkernel — strict JSON boundary compilation with receipt artifacts
- `check-runner` — `/home/sikmindz/Coding/Libraries/Primitives/check-runner` — Execution backend and check normalization primitives for forge-engine
- `check-runner-sys` — `/home/sikmindz/Coding/Libraries/Primitives/check-runner-sys` — Unsafe syscall wrappers for check-runner process-group operations
- `constraint-compiler` — `/home/sikmindz/Coding/Libraries/constraint-compiler` — Deterministic projection-to-inference graph compiler for the recursive inference kernel
- `effect-runtime` — `/home/sikmindz/Coding/Libraries/effect-runtime` — Typed side-effect intent, execution receipt, and policy primitives for RecursiveIntell runtime gates
- `forge-policy` — `/home/sikmindz/Coding/Libraries/Primitives/forge-policy` — Workspace and database safety policy primitives for forge-engine
- `forge-policy-fuzz` — `/home/sikmindz/Coding/Libraries/Primitives/forge-policy/fuzz` — No manifest description; inspect source before assuming absence.
- `kernel-conformance` — `/home/sikmindz/Coding/Libraries/kernel-conformance` — Conformance harness for recursive inference kernel authority, compiler, and oracle gates
- `mechanism-runtime` — `/home/sikmindz/Coding/Libraries/mechanism-runtime` — Typed mechanism/theory surface crate with bounded fit and refuter evaluators; not a standalone runtime
- `remote-oracle-admission` — `/home/sikmindz/Coding/Libraries/remote-oracle-admission` — Typed remote oracle admission contracts for lease, result, replay, and re-admission artifacts
- `spec-execution` — `/home/sikmindz/Coding/Libraries/spec-execution` — Typed spec and proof surface crate with bounded generated-artifact evaluators; not a compiler runtime
- `verification-adjudication` — `/home/sikmindz/Coding/Libraries/verification-adjudication` — Canonical verification disposition, promotion, refutation, and rollback decisions
- `verification-calibration` — `/home/sikmindz/Coding/Libraries/verification-calibration` — Canonical verification calibration and abstention artifacts
- `verification-control` — `/home/sikmindz/Coding/Libraries/verification-control` — Canonical verification control-plane case, plan, receipt, and ledger artifacts
- `verification-policy` — `/home/sikmindz/Coding/Libraries/verification-policy` — Canonical verification policy and approval artifacts

### Agent Runtime Governance

- `agent-graph` — `/home/sikmindz/Coding/Libraries/agent-graph` — Graph-based agent orchestration for Rust - LangGraph for the Rust ecosystem
- `agent-guard` — `/home/sikmindz/Coding/Libraries/agent-guard` — No manifest description; inspect source before assuming absence.
- `aidens-agency-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-agency-kit` — AiDENs agency policy engine — influence classification, nudge ledger, policy evaluation
- `aidens-app-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-app-kit` — Safe app builder and profile expansion with 5 built-in profiles
- `aidens-arbiter-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-arbiter-kit` — Thin arbiter facade over canonical contradiction artifacts
- `aidens-autonomous` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-autonomous` — Autonomous gap detection and task generation for closed-loop self-learning
- `aidens-boundary-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-boundary-kit` — Boundary compiler primitives — LLM structured output, canonical JSON digestion
- `aidens-budget-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-budget-kit` — Budget, retry, fanout, and stop-rule guards for agent execution
- `aidens-capability-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-capability-kit` — Runtime capability truth surfaces and support tier reporting
- `aidens-cli` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-cli` — AiDENs CLI — agent creation, doctor diagnostics, scaffold generation, receipt inspection
- `aidens-config` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-config` — Config loading, validation, redaction, and atomic apply planning
- `aidens-contracts` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-contracts` — Versioned base contracts — shared primitive artifact shapes for AiDENs
- `aidens-daemon-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-daemon-kit` — Daemon facade for queue, schedule, wake, leases, and safe mode
- `aidens-delegation-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-delegation-kit` — Delegation status surface (quarantined — status interface only)
- `aidens-governance-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-governance-kit` — Governance facade — permit checking, release readiness, authority chains
- `aidens-integration-tests` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-integration-tests` — E2E integration tests proving the unified agent framework
- `aidens-kernel-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-kernel-kit` — Kernel reasoning facade — compiler, execution, oracle, conformance gates
- `aidens-memory-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-memory-kit` — Memory facade — search, graph, integrity, receipts over semantic-memory
- `aidens-memory-tools` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-memory-tools` — Native semantic-memory, knowledge-runtime, and claim-ledger tools for AiDENs agents
- `aidens-permit-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-permit-kit` — Approval and permit model for tool dispatch gating
- `aidens-plan-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-plan-kit` — Execution-plan assembly helpers for AiDENs product surfaces
- `aidens-profile-coding` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-profile-coding` — Coding-agent profile — tool bundles, permits, budget limits
- `aidens-profile-daemon` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-profile-daemon` — Daemon profile status — safe-mode surface for autonomous operation
- `aidens-profile-desktop` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-profile-desktop` — Desktop profile status (deferred until desktop product wiring)
- `aidens-profile-memory` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-profile-memory` — Memory-agent profile status (partial/proof-only surface)
- `aidens-profile-research` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-profile-research` — Research-workbench profile status (deferred/example-only surface)
- `aidens-provider-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-provider-kit` — Provider construction, execution, and route truth — Ollama, Mock, Disabled
- `aidens-queue-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-queue-kit` — Append-only durable queue substrate for daemon execution
- `aidens-receipts` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-receipts` — Canonical receipt persistence — NDJSON append, chain verification, digests
- `aidens-repair-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-repair-kit` — Repair facade over canonical verification and Forge repair artifacts
- `aidens-runner` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-runner` — Run and turn executor — provider, tools, governance, memory, receipts
- `aidens-schedule-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-schedule-kit` — One-shot schedule occurrence construction for daemon execution
- `aidens-security-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-security-kit` — Path safety helpers and canonical tool side-effect classification
- `aidens-testkit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-testkit` — Independent reference interpreters for semantic conformance tests
- `aidens-tool-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-tool-kit` — Tool registry, exposure planning, and safe sandbox-validated dispatch
- `aidens-tui` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-tui` — Terminal UI for observing the AiDENs autonomous loop
- `aidens-wake-kit` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens-wake-kit` — Wake-signal construction for daemon queues
- `authority-delegation` — `/home/sikmindz/Coding/Libraries/authority-delegation` — Typed delegated-authority surface crate with bounded lease and policy artifacts; not an access-control runtime
- `federated-settlement` — `/home/sikmindz/Coding/Libraries/federated-settlement` — Typed treaty and settlement surface crate with bounded shared-view evaluators; not a network runtime
- `llm-tool-runtime` — `/home/sikmindz/Coding/Libraries/llm-tool-runtime` — Provider-agnostic tool contracts, registry, dispatch, and receipt plumbing for llm-pipeline
- `profile-runtime` — `/home/sikmindz/Coding/Libraries/profile-runtime` — Canonical effective constitution and profile composition runtime for the local-first AI systems stack
- `tauri-queue` — `/home/sikmindz/Coding/Libraries/tauri-queue` — Tauri integration for agent-queue background job processing

### Context Parsing Orchestration

- `context-governor` — `/home/sikmindz/Coding/Libraries/context-governor` — Crate-agnostic governed context compaction with receipts, exact fallback references, and recall quality filters
- `kernel-execution` — `/home/sikmindz/Coding/Libraries/kernel-execution` — Deterministic K2 execution baseline for recursive inference graphs
- `kernel-oracles` — `/home/sikmindz/Coding/Libraries/kernel-oracles` — Bounded exact/conservative oracle paths for the recursive inference kernel
- `llm-output-parser` — `/home/sikmindz/Coding/Libraries/llm-output-parser` — Production-grade parser for extracting structured data from LLM responses. Handles think blocks, markdown fences, malformed JSON, and real-world model output without an additional LLM call.
- `llm-pipeline` — `/home/sikmindz/Coding/Libraries/llm-pipeline` — Reusable node payloads for LLM workflows: prompt templating, Ollama calls, defensive parsing, streaming, and sequential chaining
- `recursive-kernel-core` — `/home/sikmindz/Coding/Libraries/recursive-kernel-core` — Non-authoritative recursive inference kernel schemas and operator contracts

### Compression Retrieval Inference

- `compressed-scorer` — `/home/sikmindz/Coding/Libraries/compressed-scorer` — Codec-agnostic compressed-domain scoring — estimate inner products without decompressing vectors
- `gpu-backend` — `/home/sikmindz/Coding/Libraries/gpu-backend` — Shared CUDA GPU backend for fib-quant and turbo-quant vector quantization (Hadamard rotation kernel, codebook lookup kernel, parity-verified)
- `hnsw-bench` — `/home/sikmindz/Coding/Libraries/hnsw-bench` — HNSW backend benchmark: hnsw_rs 0.3 vs usearch 2.25. Generates a receipt-bench receipt.
- `hyperquant` — `/home/sikmindz/Coding/Libraries/hyperquant` — Experimental lattice quantization primitives with explicit receipts and conservative claim boundaries
- `poly-kv` — `/home/sikmindz/Coding/Libraries/poly-kv` — Shared compressed KV-cache pool for multi-agent context. Two-tier codec policy (fib-quant cold + turbo-quant hot) with typed receipts.
- `poly-kv` — `/home/sikmindz/Coding/Libraries/poly-kv/crates/poly-kv` — Shared compressed KV-cache pool for Rust: two-tier codec policy (fib-quant cold + turbo-quant hot) with typed receipts
- `poly-kv-python` — `/home/sikmindz/Coding/Libraries/poly-kv/crates/poly-kv-python` — Optional PyO3 sidecar bindings for poly-kv bulk receipt experiments.
- `quant-codec-core` — `/home/sikmindz/Coding/Libraries/poly-kv/crates/quant-codec-core` — Shared codec/profile/shape/eval traits and typed IDs for governed compression experiments
- `quant-eval` — `/home/sikmindz/Coding/Libraries/quant-eval` — Compression and semantic search evaluation benchmark suite — codec admissibility, compression ratios, and retrieval quality
- `quant-governor` — `/home/sikmindz/Coding/Libraries/quant-governor` — Governance policy routing for governed compression — codec selection with admissibility classes and degradation receipts
- `scr-runtime-compression` — `/home/sikmindz/Coding/Libraries/scr-runtime-compression` — Runtime integration adapter for semantic-memory compression layer — CompressedSearchPath and ExactFallbackAdapter delegates to turbo-quant/fib-quant
- `turbo-quant` — `/home/sikmindz/Coding/Libraries/turbo-quant` — Experimental vector compression sidecars with PolarQuant, TurboQuant, QJL sketches, wire formats, and benchmark receipts
- `turbo-quant-semantic-memory-harness` — `/home/sikmindz/Coding/Libraries/turbo-quant/tools/semantic_memory_harness` — No manifest description; inspect source before assuming absence.

### Patch Sandbox Execution

- `effect-signature` — `/home/sikmindz/Coding/Libraries/Primitives/effect-signature` — Stable check effect signature types and hashing helpers
- `sandbox-workspace` — `/home/sikmindz/Coding/Libraries/Primitives/sandbox-workspace` — Workspace sandboxing and patch filesystem primitives
- `sandbox-workspace-fuzz` — `/home/sikmindz/Coding/Libraries/Primitives/sandbox-workspace/fuzz` — No manifest description; inspect source before assuming absence.
- `stabilizer-core` — `/home/sikmindz/Coding/Libraries/Primitives/stabilizer-core` — Bounded attempt-phase and delta policy primitives for forge-engine
- `typed-patch` — `/home/sikmindz/Coding/Libraries/Primitives/typed-patch` — Structured patch schema plus validation and apply helpers
- `typed-patch-fuzz` — `/home/sikmindz/Coding/Libraries/Primitives/typed-patch/fuzz` — No manifest description; inspect source before assuming absence.

## Other canonical Libraries crates (inspect before adding equivalents)

- `agent-queue` — `/home/sikmindz/Coding/Libraries/job-queue` — Production-grade background agent job queue system
- `ai-batch-queue` — `/home/sikmindz/Coding/Libraries/ai-batch-queue` — Model-aware batch processing queue with ETA estimation for Tauri applications
- `aidens` — `/home/sikmindz/Coding/Libraries/AiDENs/crates/aidens` — Umbrella crate re-exporting all AiDENs capabilities with one-liner quickstart
- `comfyui-rs` — `/home/sikmindz/Coding/Libraries/comfyui-rs` — Async Rust client for ComfyUI — REST, WebSocket progress, and workflow building
- `contract-schema-gen` — `/home/sikmindz/Coding/Libraries/contract-schema-gen` — Generate JSON schemas for RecursiveIntell contract and proof runtime types
- `discovery-portfolio` — `/home/sikmindz/Coding/Libraries/discovery-portfolio` — Typed discovery portfolio surface crate with bounded budget and selection evaluators; not a scheduler runtime
- `fib-quant` — `/home/sikmindz/Coding/Libraries/fib-quant` — Experimental Rust implementation of the FibQuant radial-angular vector quantization core
- `forge-engine` — `/home/sikmindz/Coding/Libraries/living-memory/living-memory` — Causal edit attribution and structured patch evaluation engine
- `forge-pilot` — `/home/sikmindz/Coding/Libraries/forge-pilot` — Closed-loop orchestrator over runtime advisories, kernel oracles, and canonical Forge export/import lanes
- `mindstate-core` — `/home/sikmindz/Coding/Libraries/Primitives/mindstate-core` — Serializable mindstate payload types for forge-engine
- `ollama-vision` — `/home/sikmindz/Coding/Libraries/ollama-vision` — Robust Ollama vision model toolkit for image tagging and captioning
- `scr-audit-adapter` — `/home/sikmindz/Coding/Libraries/scr-runtime/crates/scr-audit-adapter` — Fixture audit adapter for SCR-P0A.
- `scr-cli` — `/home/sikmindz/Coding/Libraries/scr-runtime/crates/scr-cli` — CLI for SCR-P0A fixture and schema workflows.
- `scr-kernel` — `/home/sikmindz/Coding/Libraries/scr-runtime/crates/scr-kernel` — Canonical SCR-P0A deterministic control evaluator types.
- `scr-reference` — `/home/sikmindz/Coding/Libraries/scr-runtime/crates/scr-reference` — Reference SCR-P0A evaluator entry point.

## Non-library product and distribution surfaces

- `agent-memory-kits` — host plugins, hooks, installers, benchmark runners, evidence workbench, release gate, admin preflight, authority delegation, Forge admin, context-governor audit.
- `semantic-memory-mcp` — host-facing MCP/HTTP adapter; witnessed lean surface and governed mutation adapters.
- `Gloss` — strongest end-user local knowledge application and preferred visible demonstration shell.
- `Recall`, `Recall-Coding`, `MiniRecall` — existing operator/coding/mobile memory shells; do not create another shell without explicit consolidation rationale.
- `forge-workbench` and Forge crates — verification/evidence operator workflows; reuse rather than creating another proof UI.
- `AiDENs` — autonomous runtime and governance kits; mine existing gap, proof-debt, hostile-audit, permit, budget, delegation, boundary, security, queue, provider, and scheduling components.
- `recursiveintell-web` — public portfolio/evidence index.
- `turbo-quant`, `poly-kv`/proveKV — compression research lane; do not mix into canonical truth semantics.
- ESP32-S3 repositories/crates — hardware proof lane.

## Existing cross-stack invariants

- SQLite authoritative state; append-plus-supersession rather than shadow truth.
- Bitemporal/current/historical state views.
- Claims require evidence and support judgments.
- Receipts must correspond to actual emitted/runtime behavior.
- Stable IDs flow through `stack-ids`; do not invent local identity formats casually.
- Promotion/rejection/quarantine/defer are explicit policy outcomes.
- Authority delegation and capability boundaries already exist.
- Context compaction/recovery belongs to `context-governor`, not semantic-memory duplication.
- Deterministic LLM parsing belongs to `llm-output-parser`.
- Patch validation/sandbox/check execution already have primitives.
- Compression and ANN optimizations remain optional projections, never canonical truth.

## Trees that are not canonical sources

- `_salvage_from_libraries2/`, `Libraries.bak/`, `docs/archive/`, application `_vendor/` or `vendor/`, generated fixtures, and integration snapshots.
- Duplicate package names in archived/application copies are references only. Modify the canonical `/home/sikmindz/Coding/Libraries/<crate>` implementation unless explicitly targeting a vendored release.

## Required preflight for every implementation agent

1. Read this file and `EXISTING_MEMORY_BENCHMARK_REUSE_INVENTORY.md`.
2. Search canonical manifests and source for the proposed capability and contract names.
3. Read the current plan and dirty status.
4. State which existing component will be reused or why it cannot be.
5. Add the smallest adapter or extension; do not add a parallel truth store, ledger, receipt family, benchmark framework, or operator shell.
6. Preserve claim boundaries and verify with controller-run receipts.