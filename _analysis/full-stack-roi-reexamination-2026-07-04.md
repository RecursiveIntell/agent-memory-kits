# Full-stack ROI re-examination — all 101 crates

Date: 2026-07-04
Scope: 101 crates across 3 workspaces (Libraries 64, AiDENs 37, Libraries2 salvage 10 overlap)

## Full inventory

| Workspace | Crates | LOC | Tests | Published |
|-----------|--------|-----|-------|-----------|
| Libraries | 64 | 164K | ~1552 | 25 |
| AiDENs | 37 | 59K | ~500 | 0 |
| **Total** | **101** | **223K** | **~2052** | **25** |

## What was missed in the previous audit

### AiDENs workspace — 37 crates, 59K LOC, ~500 tests — NOT PREVIOUSLY AUDITED

AiDENs builds clean (cargo check exit 0). It is a complete autonomous agent runtime with:

**aidens-contracts** (15,239 LOC, 96 tests) — typed contract surface: agent bundles, app status, artifacts, boundaries, capability turns, daemon queues, execution, operator, proof, provider, release completion, schema catalog, semantic, tool artifacts, view disclosure, view runtime. This is the type system for a full agent platform.

**aidens-autonomous** (8,260 LOC, 151 tests) — the autonomous loop driver:
- entropy_search.rs — entropy-gradient-guided domain selection (FEUT-001). Finds where knowledge is most uncertain and prioritizes those areas.
- hostile_audit.rs — cross-checks captured facts with a DIFFERENT LLM. When viscosity is Strict/Frozen, facts are cross-checked before promotion.
- viscosity.rs — adaptive runtime viscosity controller (FEUT-005). Computes composite signal from loop metrics, maps to strictness level.
- proof_debt.rs — proof-debt entropy budget. Tracks cumulative unverified claims. Debt is paid when claims are verified. Blocks promotion when debt exceeds threshold.
- gap_detector.rs (1,507 LOC) — structural and content-level gap detection over semantic memory. Issues HTTP calls to warm server, analyzes results for knowledge gaps.
- loop_driver.rs — the main autonomous loop.
- capture.rs, evaluation.rs, executor.rs, receipt.rs, task_generator.rs, missions.rs

**aidens-cli** (9,219 LOC, 50 tests) — CLI with agent, doctor, scaffold, schemas, test_agent, package commands.

**aidens-runner** (4,522 LOC, 10 tests) — execution runner.

**aidens-tool-kit** (3,609 LOC, 15 tests) — tool contracts.

**aidens-boundary-kit** (1,911 LOC, 23 tests) — boundary enforcement.

**aidens-receipts** (1,141 LOC, 6 tests) — receipt system.

**aidens-governance-kit** (887 LOC, 18 tests) — governance integration.

**aidens-memory-kit** (1,463 LOC, 8 tests) — memory integration.

### Published crate quality issues

- agent-graph: 58 downloads, 0 tests — published but untested
- quant-codec-core: 17 downloads, 0 tests — published but untested

### agent-guard — has MCP feature

agent-guard has a `mcp` feature flag (gated behind tokio dep). It defines SecurityDecision, Subject, Action, ActionType, SecurityMechanism types. It is a Linux control-plane crate for AI agent security (BPF LSM, cgroup v2, Landlock, seccomp, eBPF). Currently 294 LOC — a skeleton, not a full implementation. But the MCP feature flag means it was designed to be exposed as an MCP server.

## Highest-ROI next moves (re-ranked with full inventory)

### 1. Wire AiDENs gap_detector into the plugin stack — ROI 10/10

AiDENs gap_detector.rs is 1,507 LOC, already tested, already calls the semantic-memory HTTP server. It detects structural and content-level knowledge gaps. This is the missing "what don't I know?" layer for the memory stack.

Integration: add a `/memory-gaps` command that calls gap_detector against the warm server, returns gap report. Add it as a memory-curator skill capability.

Effort: LOW — the code exists and works. Just needs a CLI wrapper and plugin command.

### 2. Wire AiDENs proof_debt into the release-gate pipeline — ROI 9.5/10

proof_debt.rs tracks cumulative unverified claims. Every time a fact is promoted, debt is incurred. Debt is paid when verified. This is the missing enforcement layer for "no shadow truth" — it makes the claim-ledger actually accountable.

Integration: release-gate-v2 should check proof_debt before promotion. If debt exceeds threshold for the risk class, promotion is blocked until debt is paid (tests pass, audit passes, evidence provided).

Effort: LOW — the code exists. Wire it into release-gate-v2.py via a Rust helper or Python port of the budget logic.

### 3. Wire AiDENs hostile_audit into the curator skill — ROI 9/10

hostile_audit.rs cross-checks captured facts with a DIFFERENT LLM. This is exactly what the memory-curator skill needs — don't just self-verify, cross-verify with an adversarial model. When viscosity is Strict, facts get cross-checked before promotion.

Integration: add hostile audit as a curator skill step. When promoting a fact, optionally call a different LLM to verify. The plugin already has provider-kit patterns.

Effort: MEDIUM — needs a second LLM endpoint configured.

### 4. Wire AiDENs viscosity controller into the recall hook — ROI 8.5/10

viscosity.rs computes a composite signal from loop metrics and maps to strictness (Fluid/Normal/Strict/Frozen). When viscosity is high, recall should be more conservative, admission should be stricter, and facts should require more evidence before injection.

Integration: sm-recall.py checks current viscosity level, adjusts admission thresholds accordingly. When Frozen, only namespace-matched high-overlap hits are admitted.

Effort: LOW — viscosity is a signal computation, the hook just needs to read it.

### 5. Publish the Forge crate family — ROI 9/10

Still the highest publishing ROI. 12 crates, 30K LOC, ~250 tests. The standalone extraction plan is already written at /home/sikmindz/Coding/Libraries/docs/forge-standalone-extraction-plan.md. The plugin integration (verify-patch, forge-admin MCP) is already done and tested.

Effort: MEDIUM — needs README upgrades, dry-run packaging fixes, dependency chain publication.

### 6. Publish ai-batch-queue + tauri-queue + comfyui-rs + ollama-vision — ROI 8.5/10

These are the practical crates with obvious public search demand. ai-batch-queue (1,834 LOC, 20 tests) and tauri-queue (376 LOC, 2 tests) are already used by forge-workbench. comfyui-rs (1,573 LOC, 23 tests) is a complete ComfyUI client. ollama-vision (624 LOC, 2 tests) is a practical vision toolkit.

Effort: LOW — mostly README upgrades and cargo publish --dry-run checks.

### 7. Add tests to agent-graph and quant-codec-core — ROI 7/10

Both are published with 0 tests. agent-graph has 58 downloads. If someone depends on them and they break, it damages credibility. Add at least basic smoke tests.

Effort: LOW — add a few basic tests to each.

### 8. Wire agent-guard MCP feature into the pro plugin — ROI 7/10

agent-guard has an MCP feature flag. It defines security decision types. Wire it as an admin MCP server that reports security posture (which mechanisms are available: cgroup, seccomp, Landlock, BPF). This is a Linux-only pro feature for businesses that want agent process sandboxing.

Effort: MEDIUM — agent-guard is a skeleton. Needs implementation work before it's useful.

### 9. Publish the verification kit — ROI 7/10

verification-control (2,942 LOC, 13 tests), verification-policy (2,042 LOC, 4 tests), verification-adjudication (707 LOC, 2 tests), verification-calibration (120 LOC, 2 tests), receipt-bench (2,068 LOC, 27 tests), contract-schema-gen (1,173 LOC, 10 tests), kernel-conformance (2,007 LOC, 49 tests). 7 crates, ~10K LOC, ~107 tests. These are the proof/verification surface that the pro plugin uses.

Effort: MEDIUM — dependency chain is complex (contract-schema-gen depends on 24 internal crates).

### 10. Cross-engine compaction benchmark — ROI 7/10

The context-governor ROI audit flagged this: build identical-input cross-engine benchmark against Squeez/Ogham/LLMLingua where callable. This produces evidence that your compaction is competitive.

Effort: MEDIUM — needs to install and run competitor tools.

## Suggested implementation order

### Sprint F: AiDENs integration (fastest, highest ROI)
1. Wire gap_detector as /memory-gaps command
2. Wire proof_debt into release-gate-v2
3. Wire viscosity into recall hook thresholds
4. Wire hostile_audit into curator skill

### Sprint G: Publishing
5. Publish Forge family (12 crates) — READMEs + dry-run + publish
6. Publish practical crates (ai-batch-queue, tauri-queue, comfyui-rs, ollama-vision)
7. Add tests to agent-graph + quant-codec-core
8. Publish verification kit (after Forge, since verification-control depends on forge-engine)

### Sprint H: Competitive evidence
9. Cross-engine compaction benchmark
10. Agent-guard MCP skeleton wiring

## What I did NOT recommend (and why)

- Publish all 39 unpublished crates — most are support/schema crates that don't make sense standalone
- Publish AiDENs as a public product — it's an autonomous agent runtime that needs a clear product story first
- Rewrite hooks in Rust — the Python hooks work, canonicalize JSON schemas instead
- Build a new memory server — semantic-memory-mcp is the server, the pro layer adds accountability on top