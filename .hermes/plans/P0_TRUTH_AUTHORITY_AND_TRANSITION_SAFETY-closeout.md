# Hostile Audit Closeout Implementation Plan

> **For Hermes:** Execute this plan immediately using TDD and independent pre-commit review.

**Goal:** Close the remaining `agent-memory-kits` metadata-envelope injection vulnerability, verify all three audited repositories, and leave only attributable local commits.

**Architecture:** Preserve `shared/scripts/injection_framing.py` as the canonical compiler. Render each admitted memory as one escaped JSON payload between fixed envelope lines, then regenerate the packaged Codex copy byte-for-byte. Keep unrelated dirty-worktree files unstaged.

**Tech Stack:** Python 3.14, unittest/pytest, Ruff, mypy where applicable, Git, Codex CLI independent review.

---

## Evidence-backed current state

- `/home/sikmindz/Coding/Libraries/semantic-memory`: audit commit `f4cc89b`; scoped format/check/test/clippy and HNSW feature compilation passed. Unrelated `Cargo.toml`, `src/config.rs`, `src/search.rs`, and migration-example work remains unstaged.
- `/home/sikmindz/Coding/Libraries/semantic-memory-mcp`: audit commit `d232f40`; default and stable profile tests/check/clippy passed. Unrelated `Cargo.toml` and `Cargo.lock` remain unstaged.
- `/home/sikmindz/Coding/agent-memory-kits`: audit patch staged but uncommitted. Focused tests and Ruff passed. Full pytest has three unchanged external-fixture failures because `/tmp/sleeper-official` is not a Git checkout. Full mypy is blocked by duplicate copied-host module names.
- Latest independent Codex review rejected the kit patch because provenance metadata can contain newlines or the envelope terminator and spoof the textual frame.

## P0 — Close framing injection

### Task 1: Add RED regression

**Files:**
- Modify: `tests/test_injection_framing.py`

1. Create hostile values containing newlines, fake field labels, and `--- END MEMORY DATA ITEM ---` for every metadata field and content.
2. Assert output has exactly three structural lines: header, `payload_json: ...`, footer.
3. Parse the payload with `json.loads` and assert exact values remain data.
4. Run the focused test and require an expected failure against the old line-oriented format.

### Task 2: Implement JSON-safe canonical framing

**Files:**
- Modify: `shared/scripts/injection_framing.py`
- Regenerate: `codex/plugins/semantic-memory/scripts/injection_framing.py`
- Update: `tests/test_injection_framing.py`
- Update expectations: `tests/test_codex_memory_recall.py`

1. Build an ordered payload object from normalized admitted fields.
2. Serialize once with `json.dumps(..., ensure_ascii=True, separators=(",", ":"), sort_keys=True)`.
3. Emit only fixed header, one `payload_json:` line, and fixed footer.
4. Copy the canonical compiler byte-for-byte into the packaged plugin.
5. Run focused tests and require GREEN.

## P1 — Verification and review

### Task 3: Run gates

1. `python -m pytest tests/test_injection_framing.py tests/test_codex_memory_recall.py -q`
2. Package-copy smoke test.
3. Ruff on all changed Python files.
4. Full `python -m pytest -q`; classify only the unchanged Sleeper fixture failures as external blockers.
5. Run full mypy and record the existing duplicate-module blocker.
6. `git diff --cached --check` and added-line static security scan.

### Task 4: Independent review

1. Stage only the seven audit files plus canonical/shared framing and its tests.
2. Invoke Codex CLI in read-only mode against `git diff --cached`.
3. If review fails, add a RED regression and repeat; do not commit on a failed verdict.

## P2 — Commit and handoff

### Task 5: Commit attributable kit changes

1. Verify staged/unstaged separation.
2. Commit with `[verified]` prefix.
3. Do not push.

### Task 6: Final receipts

Report:
- all three commit hashes;
- RED and GREEN outputs;
- focused/full test outcomes;
- independent-review verdict;
- unavailable/pre-existing gates;
- remaining architectural `human_review` items and claim boundaries.
