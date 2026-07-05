# Highest-ROI completion plan — 2026-07-05

## Objective

Finish the current highest-ROI work without opening new speculative fronts:

1. Close dirty, already-implemented Libraries work.
2. Repair AiDENs workspace health and publish only the highest-ROI facade crates that are ready.
3. Turn Pro from a script bundle into an installable/supportable business product boundary.
4. Make Forge/CEA demonstrable through a concrete CLI/demo receipt path.
5. Preserve evidence: tests, publish receipts, release-gate packet, and a final ledger.

## Constraints

- Live state beats semantic memory snippets.
- Do not weaken product semantics to force a publish.
- Publish in dependency order only.
- Do not mix unrelated dirty work into commits.
- Every public/business claim needs either code receipt, test receipt, or explicit limitation.
- If crates.io rate-limits, wait/retry; if ownership blocks, record it honestly.

## Phase 1 — Dirty Libraries stabilization

Scope:

- `context-governor`: receipt index persistence, prune command, audit CLI surface.
- `semantic-memory-mcp`: LLM output parser tools.

Steps:

1. Review diffs and separate unrelated lock/doc churn.
2. Run:
   - `cargo test --manifest-path context-governor/Cargo.toml --all-targets`
   - `cargo fmt --manifest-path context-governor/Cargo.toml --check`
   - `cargo clippy --manifest-path context-governor/Cargo.toml --all-targets -- -D warnings`
   - `cargo test --manifest-path semantic-memory-mcp/Cargo.toml --all-targets`
3. Add/adjust tests if any feature lacks coverage.
4. Commit the dirty feature work.
5. Dry-run publish; publish if version slots and dependencies allow.

Acceptance:

- Dirty feature changes are committed or deliberately reverted.
- Tests pass.
- Published versions or documented blockers.

## Phase 2 — AiDENs health + facade publish

Scope:

Fix the current workspace failure, then publish only high-ROI facades in dependency order.

Known failure:

- `aidens-autonomous::missions::tests::is_stale_date_recent_date_not_stale`

Steps:

1. Fix stale-date test deterministically; do not weaken stale-date semantics silently.
2. Run `cargo test --workspace --all-targets` in `Libraries/AiDENs`.
3. Inspect dependency graph for target facade crates:
   - `aidens-contracts`
   - `aidens-memory-kit`
   - `aidens-governance-kit`
   - `aidens-tool-kit`
   - `aidens-runner`
   - `aidens-autonomous`
4. Add missing metadata/version fields.
5. Publish bottom-up only where dry-run passes.

Acceptance:

- AiDENs workspace green.
- High-ROI facades published or blockers recorded.

## Phase 3 — Pro packaging/productization

Scope:

Make Pro installable/supportable, not just code in a directory.

Steps:

1. Add `pro/scripts/pro-doctor.py`:
   - validates config file permissions;
   - checks license server health;
   - verifies token trust state;
   - checks Pro MCP wrapper files exist;
   - emits JSON receipt.
2. Add `pro/INSTALL.md` and `pro/MANAGED.md`.
3. Add `shared/scripts/public-claim-lint.py` for business-safe public claims.
4. Wire claim lint into release gate or provide a tested standalone command.
5. Tests for Pro doctor and claim lint.

Acceptance:

- Pro install path is testable.
- Business claims are mechanically linted.
- Plugin tests pass.

## Phase 4 — Forge/CEA demo path

Scope:

Make the published Forge stack understandable and demonstrable.

Steps:

1. Add a demo receipt path using existing `verify-patch.py` and published Forge crates where possible.
2. Prefer real `forge-pilot`/`forge-engine` CLI if present; keep fallback explicit.
3. Add `docs/forge-cea-demo.md` with one terminal demo and receipt flow diagram.
4. Add test proving fallback/real-binary selection logic.

Acceptance:

- Demo path exists.
- Receipt emitted.
- Tests pass.

## Phase 5 — Final proof and ledger

Steps:

1. Run plugin suite + Pro hardening pytest.
2. Run relevant Rust crate gates.
3. Create release-gate proof packet with isolated proof-debt store.
4. Update final ledger.
5. Commit all scoped changes.
6. Report published crates, commits, receipts, and blockers.
