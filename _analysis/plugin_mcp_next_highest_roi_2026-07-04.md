# Plugin/MCP next highest-ROI re-examination

Date: 2026-07-04
Scope: `/home/sikmindz/Coding/agent-memory-kits` plugins/MCP stack + `/home/sikmindz/Coding/Libraries` crates that can materially improve it.

Live checks used:
- `cargo metadata --no-deps --format-version 1` in `/home/sikmindz/Coding/Libraries`
- current `agent-memory-kits` plugin manifests, hooks, scripts, tests, README/plans
- current crate public API skim for verification, llm-tool-runtime, stack-ids, claim-ledger, context-governor, CEA/Forge, compressed-scorer
- previous plugin ROI implementation receipts from 2026-07-04

## Blunt ranking

The highest ROI is no longer “add more memory tools.” The highest ROI is to make the plugin stack an admission-controlled, receipt-backed, side-effect-aware memory runtime.

Top 10 next moves:

1. Expose/use context-governor `high_roi.rs` as a real plugin/MCP audit surface.
2. Replace ad-hoc Python tool receipts with `llm-tool-runtime` + `stack-ids` typed receipt contracts.
3. Turn Evidence Workbench from command-runner into a claim-ledger + verification-control proof packet pipeline.
4. Add admission-time hubness / global gating to recall results before injection.
5. Add an admin action preflight layer using `effect-runtime`, `verification-policy`, `verification-control`, and `authority-delegation`.
6. Add MCP/tool surface schema generation from `contract-schema-gen` or direct crate schemas to stop README/tool drift.
7. Add receipt-bench replay baselines for recall quality, compaction, and routing changes.
8. Wire Forge/CEA as a separate “patch verification / causal edit attribution” admin path, not daily recall.
9. Promote claim-ledger from companion MCP to shared proof sink for all material plugin operations.
10. Edit/remove stale public claims and duplicated host-local wrappers before release packaging.

## 1. Highest ROI: expose `context-governor/src/high_roi.rs`

Current finding:
`context-governor` already contains high-value functions that are almost tailor-made for this plugin stack, but the current plugin mostly exposes only compact/search/expand/diff receipt behavior.

Relevant crate APIs verified:
- `evaluate_governed_memory`
- `audit_mcp_tool_surface`
- `audit_compression_boundary`
- `evaluate_leakage_free_rag`
- `screen_knowledge_conflicts`
- `select_retrieval_route`

Why this is the top ROI:
These are exactly the tests/audits the plugin stack needs:
- Does memory governance prevent stale propagation?
- Are MCP tool descriptions creating split-instruction or unsafe selection surfaces?
- Does compression relink hostile source fragments into executable instructions?
- Did retrieval actually help, or was the model already right closed-book?
- Are retrieved facts conflicting before injection?
- Which retrieval route should fire for a query?

Recommended implementation:
- Add a `context-governor-audit` CLI/script wrapper in `agent-memory-kits/shared/scripts/`.
- Expose only admin/full MCP tools, not daily lean tools:
  - `cg_audit_tool_surface`
  - `cg_audit_compression_boundary`
  - `cg_eval_governed_memory`
  - `cg_eval_rag_leakage`
  - `cg_screen_conflicts`
  - `cg_select_retrieval_route`
- Add a doctor gate that runs `cg_audit_tool_surface` against the semantic-memory, context-governor, and claim-ledger tool manifests.

Crates involved:
- context-governor
- stack-ids for trace/digest IDs
- receipt-bench for replayable audit receipts
- claim-ledger for durable proof storage

Expected ROI: 10/10.
This is low engineering cost because the Rust crate already has the logic. It directly improves safety, README credibility, and release proof.

## 2. Replace ad-hoc Python tool receipts with `llm-tool-runtime` + `stack-ids`

Current state:
Hermes `post_tool_use` now emits compact JSON with schema/type/trace/digest/status. That is good, but it is still Python-local shape. Meanwhile `llm-tool-runtime` already has:
- `ToolRegistry`
- `ToolRuntime`
- `ToolReceipt`
- approval policy types
- receipt sink traits
- semantic-memory observation records
- starter tools for memory search, artifact read, verification, patch preview, patch submit

`stack-ids` already has:
- `TraceCtx`
- `ContentDigest`
- `Scope`
- `CrateReceiptV1`
- typed IDs

Recommended implementation:
- Define one canonical JSON schema for plugin tool receipts matching `llm-tool-runtime::ToolReceipt` and `stack_ids::TraceCtx` concepts.
- Keep hooks in Python for host compatibility, but make their JSON shape isomorphic to the Rust crate types.
- Add a tiny Rust helper later if needed: `tool-receipt-normalize`, which reads hook payload JSON and emits canonical receipt JSON.
- Store only digest/status/summary in semantic-memory; store full receipt in a local receipt directory or claim-ledger bundle.

Crates involved:
- llm-tool-runtime
- stack-ids
- claim-ledger
- semantic-memory

Expected ROI: 9.5/10.
This creates the trace spine all hosts can share. It also stops future drift between Hermes/Codex/Claude hook formats.

## 3. Upgrade Evidence Workbench into a real claim-ledger + verification pipeline

Current state:
`evidence-workbench.py` runs commands and emits a proof packet. `proof-packet.py` joins command receipt, claim JSON, and disposition JSON and now fails closed on unknown command status.

Gap:
It does not yet use the richer crates that already exist:
- `verification-control`: ReleaseGateCaseV1, CheckPlan, ControlReceipt, TerminalDisposition
- `verification-policy`: ReleasePolicyProfileV1, approval/permit surfaces
- `verification-adjudication`: promotion/refutation/rollback decisions
- `verification-calibration`: calibration/abstention artifacts
- `claim-ledger`: Claim, EvidenceBundle, SupportJudgment, SupportAdmissionReceipt, ledger verify/export
- `receipt-bench`: benchmark receipt substrate

Recommended implementation:
- Add `shared/scripts/release-gate-v2.py` or Rust CLI wrapper that emits:
  - ReleaseGateCaseV1
  - CheckPlan
  - command receipts
  - claim-ledger claim/evidence/support judgment
  - verification-adjudication disposition
  - final proof packet digest
- Keep old `evidence-workbench.py` as a simple fallback.
- Add `cl_ledger_verify` and `cl_export_bundle` to the release gate’s final command list.

Crates involved:
- verification-control
- verification-policy
- verification-adjudication
- verification-calibration
- claim-ledger
- receipt-bench
- stack-ids

Expected ROI: 9/10.
This turns “receipts” from a good script into a coherent proof product.

## 4. Add admission-time hubness/global gating before memory injection

Recall input surfaced a current research point: anisotropic embeddings create hubs; admission-time global gating can block low-quality ubiquitous neighbors. This maps directly to your plugin pain: memory recall should be discovery, not proof, and should not inject generic/stale/hub candidates.

Current state:
Hooks filter namespaces, noisy autorecall hits, overlap, top score, and score bands. Good start.

Missing:
- No persistent hubness statistics.
- No candidate admission ledger.
- No “why this hit was admitted/rejected” receipt.
- No recall-quality benchmark proving the filter improved injected context.

Recommended implementation:
- Add `recall-admission.jsonl` receipt store with candidate-level fields:
  - query_hash
  - result_id
  - namespace
  - score/cosine
  - global_hit_frequency
  - namespace_hit_frequency
  - stale/superseded/noisy flags
  - admitted bool
  - reject_reason
- Use semantic-memory search receipts if present, otherwise hook-local JSONL.
- Add global gating thresholds:
  - reject high-frequency hubs unless exact term overlap or namespace match is strong
  - demote generic project/profile facts on task-specific queries
  - boost exact current repo namespace hits
- Benchmark with `receipt-bench` fixtures.

Crates involved:
- semantic-memory
- context-governor `select_retrieval_route`
- receipt-bench
- stack-ids
- compressed-scorer/turbo-quant later if measuring compressed retrieval paths

Expected ROI: 9/10.
This directly improves day-to-day usefulness. It also gives a publishable “agent memory recall quality” story.

## 5. Add side-effect/admin action preflight using effect/delegation/policy crates

Current state:
The plugin now has a `semantic-memory-admin` path. That is good. But admin tools include maintenance, hard deletes, imports, re-embedding, profile switches, export bundles, and proof packet operations. These are side-effecting operations.

The relevant crates were easy to miss because their names sound broad, but they are exactly suited here:
- `effect-runtime`: effect intent, preflight report, commit decision, execution receipt, compensation plan
- `authority-delegation`: authority lease, delegation bundle, break-glass grant, acting-on-behalf receipt
- `attestation-exchange`: attestation envelope, trust roots, transparency receipt
- `verification-policy`: approval profiles and execution permits
- `verification-control`: effect review cases and block receipts

Recommended implementation:
- Add admin action preflight for these operations:
  - hard delete namespace/fact
  - import envelope
  - re-embed all
  - reconcile/vacuum
  - claim-ledger export bundle
  - release-gate publish/promotion
- Emit `EffectIntentV1` and `EffectPreflightReportV1` JSON before running the operation.
- If policy blocks, emit `EffectBlockReceiptV1` and do not run.
- For allowed operations, emit `EffectExecutionReceiptV1` after.

Expected ROI: 8.5/10.
This makes the plugin stack feel operator-grade instead of “a bag of scripts.”

## 6. Generate MCP/tool schemas and docs with `contract-schema-gen`

Current state:
README/docs mention 61 tools in places, while live doctor saw 41 tools in the configured lean profile. That may be explainable by profiles, but it is an easy trust-loss point if not mechanically generated.

`contract-schema-gen` depends on many of the exact crates that define your artifact contracts:
- verification-control/policy/adjudication/calibration
- semantic-memory
- forge-pilot
- mechanism/effect/profile/runtime crates
- etc.

Recommended implementation:
- Add `scripts/generate-tool-surface-docs.py` or Rust helper that captures live MCP `tools/list` for lean/standard/full/admin and writes a generated markdown/json artifact.
- Add generated docs for companion MCPs:
  - semantic-memory lean/standard/full/admin tool counts
  - context-governor tool count + audit tools when added
  - claim-ledger tool count
- Add CI/doctor check: README advertised counts must match generated tool-surface artifact.

Crates involved:
- contract-schema-gen
- semantic-memory-mcp
- context-governor
- claim-ledger
- stack-ids

Expected ROI: 8/10.
This prevents embarrassing public mismatch and makes plugin marketplaces easier.

## 7. Use `receipt-bench` as the regression harness for recall/compaction/routing

Current state:
Agent-memory-kits already has fixtures:
- `shared/fixtures/code-search.jsonl`
- `conversation-recall.jsonl`
- `contradiction-check.jsonl`

`receipt-bench` already has:
- `SMQueryFixture`
- `SMBenchmarkReport`
- `run_sm_benchmark`
- recall@k, nDCG@k, reciprocal rank
- comparison reports

Recommended implementation:
- Replace ad-hoc recall eval scripts with receipt-bench-backed reports where possible.
- Every routing/filter change should produce a before/after report hash.
- Add a simple command:
  - `scripts/benchmark-recall-receipted.sh`
- Add release gate requirement: recall benchmark does not regress beyond threshold.

Expected ROI: 8/10.
This turns recall tuning from vibes into receipts.

## 8. Forge/CEA plugin path: high ROI, but keep separate from daily memory

Current finding:
Forge/CEA was underweighted earlier. The dependency graph confirms it is a coherent patch-verification stack:
- `forge-engine` depends on `cea-core`, `cea-store`, `cea-sqlite`, `typed-patch`, `check-runner`, `claim-ledger`, `llm-tool-runtime`, `semantic-memory`, `stack-ids`, etc.
- `cea-core` provides causal edit attribution, effect signatures, prediction, confidence.
- `typed-patch` provides structured patch schema/apply/validation.
- `check-runner` normalizes command/check execution.

Highest ROI plugin use:
- Add a separate admin command/tool path: “verify this patch/change before apply.”
- Input: patch or changed files + intended claim.
- Flow:
  - typed-patch validates patch
  - sandbox-workspace applies in temp workspace
  - check-runner runs tests/checks
  - cea-core attributes passing/failing effects to edits
  - claim-ledger records claim/evidence
  - verification-adjudication promotes/rejects

Do not add this to daily lean memory tools. It belongs in admin/full/release-gate workflow.

Crates involved:
- forge-engine
- forge-pilot
- typed-patch
- sandbox-workspace
- check-runner
- cea-core/cea-store/cea-sqlite
- effect-signature
- claim-ledger
- verification-* stack

Expected ROI: 8/10 for your current projects, 6/10 for broad public plugin until polished.

## 9. Promote claim-ledger from companion to proof sink

Current state:
Claim-ledger MCP exists and exposes 5 `cl_*` tools. But most plugin scripts still create their own JSON receipts separately.

Recommended implementation:
- For material operations, write both:
  - local compact receipt JSON
  - claim-ledger entry/export bundle
- Material operations include:
  - release gates
  - memory namespace deletions
  - imports
  - compaction certification
  - MCP surface audit
  - recall benchmark baseline changes
- Make `cl_ledger_verify` part of doctor/deep validation.

Expected ROI: 7.5/10.
It consolidates proof instead of scattering receipts across scripts.

## 10. Remove/edit/update low-signal or stale public surface

Items to clean before release/public push:

- README/tool-count drift:
  - top-level docs mention 61 tools; current doctor in lean saw 41 tools. Explain profile counts mechanically or generate them.
- Duplicate host wrappers:
  - Claude/Codex/Hermes each carry copies of similar scripts. Keep host wrappers tiny and move shared logic to `shared/scripts`.
- Python `__pycache__` appeared in file discovery but is not tracked/untracked by git. Ensure `.gitignore` prevents future package contamination.
- Avoid adding admin tools to daily profile. `semantic-memory-admin` is correct; keep it separated.
- Remove or reword any “proves correctness” phrasing. Receipts prove command execution and boundaries, not total correctness.

Expected ROI: 7/10.
Trust polish matters because this project is public-facing.

## Suggested implementation order

### Sprint A: fastest high-ROI foundation
1. Add context-governor high_roi audit wrapper + tests.
2. Add generated tool-surface report and doctor check.
3. Add recall-admission JSONL receipts with hubness/global frequency counters.
4. Add receipt-bench recall benchmark command.

### Sprint B: proof pipeline
5. Evidence Workbench v2 using claim-ledger + verification-control/adjudication.
6. Make claim-ledger verification part of doctor deep.
7. Add stack-ids trace IDs to all generated receipts.

### Sprint C: side-effect safety
8. Admin preflight using effect-runtime + verification-policy/control.
9. Block hard deletes/imports/re-embed-all without effect receipt.
10. Add authority-delegation for operator/admin leases if/when multi-agent workers use admin tools.

### Sprint D: Forge/CEA
11. Add `verify-patch` admin workflow using typed-patch/sandbox/check-runner/CEA.
12. Only then consider exposing it as a user-facing command.

## Kill / do-not-do list

- Do not move all verification/admin/proof tools into daily lean MCP.
- Do not rewrite all hooks in Rust immediately. First canonicalize JSON schemas; wrappers are fine.
- Do not claim memory recall is proof. Keep “discovery, not proof” visible.
- Do not add graph-heavy recall by default for simple lookups. Keep GraphRAG tools as deliberate/admin/research paths.
- Do not put Forge/CEA into pre-LLM recall. It is patch-verification/release-gate infrastructure.
- Do not publish plugin docs with hand-maintained tool counts.

## One-line verdict

The next absolute highest ROI is to use your already-written governance crates as the plugin stack’s missing control plane: context-governor high_roi audits, llm-tool-runtime/stack-ids receipts, verification/claim-ledger proof packets, and admission-time recall gating. That turns the plugins from “memory add-on” into an operator-grade evidence system.
