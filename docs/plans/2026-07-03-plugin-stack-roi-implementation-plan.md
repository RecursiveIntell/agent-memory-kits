# Plugin Stack ROI Implementation Plan

> **For Hermes:** Execute this plan in priority order. Use TDD for code changes; every shipped item needs a receipt from targeted tests/smokes.

**Goal:** Turn the semantic-memory agent kits from mostly separate memory/compaction/provenance pieces into a reliable, receipt-backed plugin stack, starting with the P0 defects that make current Tier-0 claims unsafe.

**Architecture:** Keep Hermes core narrow. Put host-specific behavior in agent-memory-kits hooks/scripts/skills, keep deterministic compaction in context-governor, and use semantic-memory-mcp/claim-ledger/verification crates as external companions. Every runtime claim must be backed by a test, hook smoke, or receipt.

**Tech Stack:** Python hook scripts, Bash hook wrappers, JSON plugin manifests, Rust context-governor CLI/library, semantic-memory-mcp HTTP/MCP, claim-ledger, stack-ids/receipt-bench/verification crates for later phases.

---

## Current state checked

Date: 2026-07-03

Primary repos:
- `/home/sikmindz/Coding/agent-memory-kits`
- `/home/sikmindz/.hermes/hermes-agent`
- `/home/sikmindz/Coding/Libraries/context-governor`
- `/home/sikmindz/Coding/Libraries/semantic-memory-mcp`

Evidence:
- `agent-memory-kits/hermes/plugin.json` declares four hooks but the matching files/directories are absent.
- `agent-memory-kits/hermes/README.md` claims Hermes Tier-0 lifecycle hooks.
- Claude and Codex kits contain working hook references and scripts that can be ported/adapted.
- Hermes context-governor adapter mutates compacted messages after Rust compaction and stores the original Rust response. This can make stored receipt `compacted_messages` diverge from final messages returned to the model.
- context-governor CLI exposes `compact`, `store`, `expand`, `search`, `status`, `diff`, `boundary-audit` but not final-emission receipt finalization.
- Current context-governor store on this host has 64 receipts and ~39 MB; `index_built=false`.

## Scope boundary

This plan implements P0 first, then proceeds through P1/P2 only after P0 is verified.

P0 shipped in this session if possible:
1. Fix Hermes Tier-0 hook manifest/files.
2. Fix context-governor final emitted receipt integrity.
3. Verify Tier-0 transcript compaction hook behavior is real, not a no-op.

P1/P2 planned but not started until P0 receipts are green:
- real semantic-memory archive bridge;
- Codex RL routing feedback;
- canonical server-side routing/classification;
- admin/full MCP profile path;
- Evidence Workbench/release-gate;
- typed tool receipts and stack-ids trace spine;
- persistent receipt index/lifecycle.

---

## Phase 0: P0 — stop false Tier-0/plugin receipt claims

### Task 0.1: Add validation for Hermes plugin hook files

**Objective:** Catch manifest/file drift before shipping.

**Files:**
- Create/modify: `shared/scripts/doctor_core.py` or a focused validation script if doctor_core is not suitable.
- Test/verification: command that checks `hermes/plugin.json` hook paths exist and are executable/readable.

**Steps:**
1. Write a failing check that reads `hermes/plugin.json` and asserts each declared hook path exists.
2. Run it and verify it fails on missing Hermes hook files.
3. Add missing files in Task 0.2.
4. Re-run and verify pass.

### Task 0.2: Restore Hermes hook files declared by manifest

**Objective:** Make Hermes Tier-0 hook claims mechanically true and fail-open.

**Files:**
- Create: `hermes/hooks/common.py`
- Create: `hermes/hooks/sm-recall.py`
- Create: `hermes/hooks/sm-auto-edge.sh`
- Create: `hermes/hooks/sm-conversation-capture.py`
- Create: `hermes/scripts/sm-primer.sh`
- Modify if needed: `hermes/plugin.json`
- Modify docs if behavior differs: `hermes/README.md`

**Implementation notes:**
- Prefer the Codex Python hook common/recall code because it is portable and already has namespace/noise filtering.
- Use Bash primer wrapper or copy Claude primer behavior with path-safe resolution.
- Every hook must fail open: malformed stdin, missing binary, missing server, or timeout exits 0.
- Do not claim automatic writes unless a hook actually writes.

**Acceptance:**
- `python -m json.tool hermes/plugin.json` passes.
- every path in `hermes.plugin.json.hermes.hooks` exists.
- shell hooks are executable.
- Python hooks compile with `python -m py_compile`.
- basic stdin fixture returns either valid hook JSON or exits 0 silently.

### Task 0.3: Fix context-governor final emitted receipt integrity

**Objective:** Ensure stored receipt represents final compacted messages returned by the adapter.

**Files:**
- Modify: `/home/sikmindz/.hermes/hermes-agent/plugins/context_engine/context_governor/__init__.py`
- Test: `/home/sikmindz/.hermes/hermes-agent/tests/plugins/test_context_governor_plugin.py`

**Desired behavior:**
After all adapter mutations, the stored response's `compacted_messages` must match the returned compacted messages. Receipt count/hash fields must be updated or finalization metadata must explicitly record adapter mutation from the Rust receipt.

**TDD steps:**
1. Add failing test that forces a post-Rust mutation, e.g. orphan tool pair or LLM summary replacement.
2. After `engine.compress`, load the stored receipt JSON and assert `compacted_messages` equals the returned compacted messages after normalization.
3. Verify RED.
4. Implement adapter finalization before `_store_response(response)`.
5. Verify GREEN with targeted plugin tests.

**Acceptance:**
- Stored receipt compacted messages equal final emitted messages.
- Test covers at least one sanitizer mutation and one LLM summary replacement mutation.
- Existing context-governor plugin tests pass.

### Task 0.4: Verify Tier-0 transcript compaction hook behavior

**Objective:** Prove context-governor hooks receive actual transcript/messages and store searchable receipts.

**Files:**
- Existing: `hermes/scripts/context-governor-compact.py`
- Existing: `codex/plugins/semantic-memory/hooks/context-governor-compact.py`
- Existing: `claude/plugins/semantic-memory/scripts/context-governor-compact.py`

**Steps:**
1. Run each script with a fixture containing `messages`.
2. Verify it emits valid hook context and/or stored receipt.
3. Run with empty stdin and verify fail-open without false success.
4. If a host hook does not provide transcript payloads in reality, document the boundary and add a doctor warning.

---

## Phase 1: P1 — make memory/routing/admin surfaces real

### Task 1.1: Wire real semantic-memory archive bridge

Only after P0. Add host adapter path that writes source-backed records to semantic-memory and records real fact/document IDs in context-governor receipts. Do not archive LLM summaries as durable facts unless marked summary/heuristic with evidence refs.

### Task 1.2: Add Codex RL routing feedback

Add `/record-outcome` call to Codex `memory-recall.py`, mirroring Claude's score-based heuristic.

### Task 1.3: Remove duplicate hook classifiers

Expose/use server-side classification/planning consistently. Hooks should prefer `/search-routed` route metadata instead of local A/B/C/D/E classifier drift.

### Task 1.4: Add admin/full profile path

Daily MCP stays lean. Maintenance/curator skills get `semantic-memory-admin` or a documented profile switch so advertised tools are reachable.

---

## Phase 2: P2 — evidence workbench and trace spine

### Task 2.1: Evidence Workbench/release-gate

Join release-gate, claim-ledger, semantic-memory evidence refs, verification-* crates, receipt-bench, and stack-ids into one proof packet workflow. No done claim unless disposition is promote.

### Task 2.2: Typed tool/action receipts

Post-tool hooks produce traceable tool receipts using stack-ids-compatible IDs/digests and receipt-bench where appropriate.

### Task 2.3: Receipt index/lifecycle

Add persistent context-governor receipt index, retention policy, lineage, and richer `context_status`.

---

## Verification gauntlet

Run after each shipped phase:

```bash
cd /home/sikmindz/Coding/agent-memory-kits
python -m json.tool hermes/plugin.json >/dev/null
python -m py_compile hermes/hooks/*.py hermes/scripts/*.py
python scripts/validate-all-kits.sh
python hermes/scripts/doctor-all.py --deep
```

For Hermes context-governor adapter:

```bash
cd /home/sikmindz/.hermes/hermes-agent
PYTHONPATH=$PWD python -m pytest tests/plugins/test_context_governor_plugin.py -q -o 'addopts='
PYTHONPATH=$PWD python - <<'PY'
from plugins.context_engine import load_context_engine
engine = load_context_engine('context_governor')
print(type(engine).__name__, engine.name, engine.is_available())
PY
```

For context-governor crate if Rust code changes:

```bash
cd /home/sikmindz/Coding/Libraries/context-governor
cargo fmt --check
cargo test --all-targets
cargo clippy --all-targets -- -D warnings
```

## Claim boundary

Do not claim the full plugin stack is complete until P0-P2 pass. After P0 only, safe claim is:
"Hermes hook manifest drift and context-governor final receipt integrity were remediated and verified with targeted tests/smokes. Evidence Workbench and long-run receipt lifecycle remain planned P1/P2 work."
