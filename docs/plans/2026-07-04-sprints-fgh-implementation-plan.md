# Full-stack ROI implementation plan — Sprints F, G, H

> **For Hermes:** Implement this plan in sprint order (F, G, H). Use TDD for all behavior changes. Every shipped item needs a receipt from targeted tests.

**Goal:** Wire 4 AiDENs modules into the plugin stack, publish the Forge family + practical crates, add tests to untested published crates, wire agent-guard MCP, and build the cross-engine compaction benchmark.

**Architecture:** AiDENs modules already exist and call the semantic-memory HTTP server. They need thin Python wrappers and plugin commands. Publishing requires README upgrades + dry-run checks. No new Rust crates to build — just wiring and packaging.

**Tech Stack:** Python wrappers, Rust crates (already compiled), cargo publish, semantic-memory HTTP, AiDENs gap_detector/proof_debt/viscosity/hostile_audit.

---

## Source inventory checked

- AiDENs workspace: 37 crates, 59K LOC, ~500 tests, cargo check exit 0
- aidens-autonomous: 8,260 LOC, 151 tests — contains gap_detector (1,507 LOC), proof_debt (438 LOC), hostile_audit (180 LOC), viscosity (373 LOC), loop_driver, executor, capture, evaluation
- All AiDENs autonomous modules call the semantic-memory warm HTTP server via HTTP
- Libraries workspace: 64 crates, 164K LOC, ~1552 tests, 25 published
- agent-graph: published, 0 tests, 58 downloads
- quant-codec-core: published, 0 tests, 17 downloads
- agent-guard: 294 LOC, MCP feature flag, SecurityDecision/Subject/Action types
- Forge family: 12 crates, 30K LOC, ~250 tests, extraction plan already written
- Full ROI report: /home/sikmindz/Coding/agent-memory-kits/_analysis/full-stack-oi-reexamination-2026-07-04.md

---

## Sprint F: AiDENs integration (4 tasks, all LOW effort)

### Task F1: Wire gap_detector as /memory-gaps command

**Objective:** Add a /memory-gaps command that calls AiDENs gap_detector against the warm semantic-memory server and returns a gap report.

**Files:**
- Create: `shared/scripts/memory-gaps.py` — Python wrapper that calls the AiDENs gap_detector via HTTP or direct Rust binary
- Create: `hermes/commands/memory-gaps.md` — command doc
- Create: `tests/test_memory_gaps.py`
- Modify: `hermes/plugin.json` — add /memory-gaps command

**Implementation:**
The gap_detector calls semantic-memory HTTP /search and analyzes results for structural gaps (missing namespaces, thin coverage) and content gaps (shallow facts, missing relationships). The Python wrapper will:
1. Call the warm HTTP server /search for a given domain/namespace
2. Analyze results for gaps (low hit count, shallow content, missing graph edges)
3. Emit a gap report JSON with schema GapReportV1
4. Fail open if server unavailable

Since the gap_detector is Rust, the wrapper will either:
- Call a compiled gap-detector binary if available
- Fall back to a pure-Python implementation that queries /search and analyzes results

**Steps:**
1. Write failing test
2. Implement memory-gaps.py with Python fallback
3. Add command to plugin.json
4. Run test, commit

### Task F2: Wire proof_debt into release-gate-v2

**Objective:** release-gate-v2 checks proof_debt before promotion. If unverified claim debt exceeds threshold for the risk class, promotion is blocked.

**Files:**
- Create: `shared/scripts/proof_debt.py` — Python module tracking cumulative unverified claims
- Modify: `shared/scripts/release-gate-v2.py` — add proof_debt check before adjudication
- Create: `tests/test_proof_debt.py`

**Implementation:**
proof_debt.py implements:
- RiskClass enum: Low, Medium, High, Critical
- ProofDebtBudget class with thresholds per risk class
- incur(claim_id, namespace, risk_class) — record new debt, return entry ID
- pay(entry_id, payment_method) — mark debt as paid
- is_blocked(risk_class) — True if debt exceeds threshold
- status() — return current debt summary

release-gate-v2.py: after adjudication, before final disposition:
1. Load proof_debt budget from JSONL store
2. incur debt for the claim being promoted
3. If is_blocked(risk_class) and disposition is "promote", change to "quarantine" with reason "proof debt exceeds threshold for {risk_class}"
4. If disposition is "reject", pay the debt (claim was rejected, no debt owed)

### Task F3: Wire viscosity into recall hook thresholds

**Objective:** sm-recall.py reads current viscosity level and adjusts admission thresholds. When Frozen, only namespace-matched high-overlap hits are admitted.

**Files:**
- Create: `shared/scripts/viscosity.py` — Python module computing viscosity signal
- Modify: `hermes/hooks/sm-recall.py` — read viscosity, adjust thresholds
- Create: `tests/test_viscosity.py`

**Implementation:**
viscosity.py implements:
- StrictnessLevel enum: Fluid, Normal, Strict, Frozen
- ViscosityController class:
  - record(metrics) — record loop metrics (success rate, error rate, contradiction count)
  - compute_signal() — compute composite signal
  - level() — return current StrictnessLevel
- Persists to JSON file at $SEMANTIC_MEMORY_DIR/viscosity.json

sm-recall.py: after loading viscosity level:
- Fluid: use current thresholds (default)
- Normal: raise mintop from 0.58 to 0.62, reduce max_hits from 4 to 3
- Strict: raise mintop to 0.68, reduce max_hits to 2, require min_overlap 2
- Frozen: raise mintop to 0.75, reduce max_hits to 1, require namespace_match

### Task F4: Wire hostile_audit into curator skill

**Objective:** memory-curator skill can optionally cross-verify facts with a different LLM before promotion.

**Files:**
- Create: `shared/scripts/hostile-audit.py` — Python script that sends a fact to a second LLM for verification
- Modify: `hermes/skills/memory-curator/SKILL.md` — add hostile audit step
- Create: `tests/test_hostile_audit.py`

**Implementation:**
hostile-audit.py:
1. Takes --fact-json (the fact content to verify), --auditor-url (second LLM endpoint), --auditor-model
2. Sends the fact to the auditor LLM with a prompt: "Verify this claim against your knowledge. Is it accurate? Reply with {valid: true/false, reason: ...}"
3. Parses the response using llm-output-parser patterns
4. Emits an AuditResult JSON: {schema: HostileAuditResultV1, fact_id, auditor_model, valid, reason, timestamp}
5. Fail open if auditor URL not set

**Sprint F gate:**
```bash
python -m unittest discover tests/ -v
python shared/scripts/release-gate-v2.py --claim "Sprint F: AiDENs integration wired" --cmd "python -m unittest discover tests/" --cwd . --no-memory --out-dir /tmp/sprint-f-proof
```

---

## Sprint G: Publishing (4 tasks)

### Task G1: Publish Forge family (12 crates)

**Objective:** Publish the 12 Forge crates to crates.io in dependency order.

**Files:**
- Modify: READMEs for all 12 Forge crates (add diagrams, examples, non-goals, integration maps)
- Run: cargo publish --dry-run for each crate in order
- Run: cargo publish for each crate in order

**Publication order:**
Phase 1 (no forge internal deps): effect-signature, forge-policy, sandbox-workspace, typed-patch, stabilizer-core, mindstate-core, check-runner, cea-core, cea-store, cea-sqlite
Phase 2: forge-engine (depends on all Phase 1)
Phase 3: forge-pilot (depends on forge-engine)

**Steps per crate:**
1. Upgrade README with 7 required sections
2. Run cargo publish --dry-run -p <crate>
3. Fix any packaging issues
4. cargo publish -p <crate>
5. Record version + timestamp

### Task G2: Publish practical crates (4 crates)

**Objective:** Publish ai-batch-queue, tauri-queue, comfyui-rs, ollama-vision.

**Steps:** Same as G1 — README upgrade, dry-run, publish.

### Task G3: Add tests to agent-graph + quant-codec-core

**Objective:** Add basic smoke tests to the two published crates with 0 tests.

**Files:**
- Create: `agent-graph/tests/smoke.rs` — basic create/query/delete test
- Create: `quant-codec-core/tests/smoke.rs` — basic encode/decode test
- Run: cargo test -p agent-graph, cargo test -p quant-codec-core
- Publish patch versions with tests

### Task G4: Publish verification kit (7 crates)

**Objective:** Publish verification-control, verification-policy, verification-adjudication, verification-calibration, receipt-bench, contract-schema-gen, kernel-conformance.

**Dependency note:** contract-schema-gen depends on 24 internal crates. It may need to be published last or made optional. verification-control depends on llm-tool-runtime and semantic-memory-forge (both already published).

**Steps:** Same as G1.

**Sprint G gate:**
```bash
# Verify all published crates are findable
cargo search forge-engine
cargo search ai-batch-queue
cargo search verification-control
cargo search receipt-bench
```

---

## Sprint H: Competitive evidence + agent-guard (2 tasks)

### Task H1: Cross-engine compaction benchmark

**Objective:** Build identical-input cross-engine benchmark against Squeez, Ogham, and Hermes built-in compaction. Produce a receipt-bench report comparing compression ratio, receipt integrity, and recall stability.

**Files:**
- Create: `shared/scripts/benchmark-compaction-cross-engine.py`
- Create: `tests/test_benchmark_compaction.py`

**Implementation:**
1. Prepare a set of test transcripts (reuse context-governor fixtures if available)
2. For each engine (Hermes context-governor, Squeez if installed, Ogham if installed, built-in head/tail):
   a. Feed identical transcript
   b. Capture compressed output
   c. Measure: token count before/after, compression ratio, time
   d. Check: is exact fallback available? Can omitted content be recovered?
3. Emit receipt-bench JSON with per-engine comparison
4. Fail open if competitor tools not installed

### Task H2: Wire agent-guard MCP skeleton into pro plugin

**Objective:** Add agent-guard as an admin MCP server that reports security posture (which Linux mechanisms are available: cgroup, seccomp, Landlock, BPF).

**Files:**
- Create: `shared/scripts/agent-guard-mcp.py` — Python MCP server wrapping agent-guard
- Modify: `pro/plugin.json` — add agent-guard MCP server
- Create: `tests/test_agent_guard_mcp.py`

**Implementation:**
1. Check which Linux security mechanisms are available on the host
2. Expose as MCP tool: agent_guard_security_posture → returns available mechanisms
3. Expose as MCP tool: agent_guard_check_process → check if a process is sandboxed
4. All admin-only, pro plugin only

**Sprint H gate:**
```bash
python -m unittest discover tests/ -v
python shared/scripts/benchmark-compaction-cross-engine.py --out /tmp/compaction-benchmark.json
```

---

## Final gauntlet

```bash
cd /home/sikmindz/Coding/agent-memory-kits
python -m unittest discover tests/ -v
python shared/scripts/doctor_core.py --host hermes --deep --receipt /tmp/final-doctor.json
python shared/scripts/release-gate-v2.py --claim "Sprints F+G+H complete" --cmd "python -m unittest discover tests/" --cwd . --no-memory --out-dir /tmp/final-proof
```

---

## Claim boundary

After Sprint F: "AiDENs gap detection, proof debt, viscosity, and hostile audit are wired into the plugin stack with targeted tests."
After Sprint G: "Forge family (12 crates), practical crates (4), and verification kit (7 crates) are published to crates.io. agent-graph and quant-codec-core now have tests."
After Sprint H: "Cross-engine compaction benchmark produces evidence against competitors. agent-guard MCP skeleton is wired into the pro plugin."

Do NOT claim:
- "AiDENs is a public product" — it is an internal autonomous runtime, not a published product
- "Forge is production-ready" — it is tested but not battle-tested in production
- "Agent-guard provides full sandboxing" — it is a skeleton that reports posture, not a full implementation