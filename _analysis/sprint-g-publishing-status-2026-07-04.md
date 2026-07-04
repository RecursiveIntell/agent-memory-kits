# Sprint G publishing status — 2026-07-04

## Dry-run results

### Phase 1 — no internal deps (can publish immediately after commit)

| Crate | Dry-run | Issue |
|-------|---------|-------|
| effect-signature | PASS | None |
| forge-policy | PASS | None |
| mindstate-core | PASS | None |

### Phase 1 — depends on Phase 1 crates (need earlier crates published first)

| Crate | Dry-run | Blocked by |
|-------|---------|------------|
| sandbox-workspace | FAIL | needs forge-policy on crates.io |
| typed-patch | FAIL | needs forge-policy + sandbox-workspace on crates.io |
| stabilizer-core | FAIL | needs typed-patch on crates.io |
| check-runner | FAIL | needs effect-signature + forge-policy + sandbox-workspace on crates.io |
| cea-core | FAIL | needs check-runner + typed-patch on crates.io |
| cea-store | FAIL | needs cea-core + check-runner on crates.io |
| cea-sqlite | FAIL | needs cea-core + cea-store + forge-policy + check-runner on crates.io |
| check-runner-sys | not checked | support crate, publish only if needed |

### Phase 2 — depends on all Phase 1

| Crate | Dry-run | Blocked by |
|-------|---------|------------|
| forge-engine | not checked | needs all Phase 1 crates on crates.io |

### Phase 3 — depends on forge-engine

| Crate | Dry-run | Blocked by |
|-------|---------|------------|
| forge-pilot | not checked | needs forge-engine on crates.io |

## Cargo.toml fixes applied

- Removed `publish = false` from 10 Primitives Cargo.toml files
- Added basic `description` field to crates that were missing it

## Remaining work before publishing

1. Commit the Cargo.toml changes (publish = false removal + descriptions)
2. Add README content to each crate (7 required sections per the extraction plan)
3. Add license, repository, homepage, documentation fields to each Cargo.toml
4. Publish in dependency order: effect-signature, forge-policy, mindstate-core → sandbox-workspace, typed-patch, stabilizer-core, check-runner → cea-core, cea-store, cea-sqlite → forge-engine → forge-pilot
5. After each publish, verify the next crate's dry-run passes

## Practical crates (G2) — separate from Forge family

| Crate | LOC | Tests | Status |
|-------|-----|-------|--------|
| ai-batch-queue | 1,834 | 20 | needs dry-run check |
| tauri-queue | 376 | 2 | needs dry-run check |
| comfyui-rs | 1,573 | 23 | needs dry-run check |
| ollama-vision | 624 | 2 | needs dry-run check |

These have fewer internal deps and may publish more easily.

## Published crates with 0 tests (G3)

| Crate | Downloads | Tests needed |
|-------|-----------|-------------|
| agent-graph | 58 | smoke test: create/query/delete |
| quant-codec-core | 17 | smoke test: encode/decode |