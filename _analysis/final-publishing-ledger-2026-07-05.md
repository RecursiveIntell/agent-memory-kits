# Final publishing ledger — 2026-07-05

Scope: finish the publishable non-queue crates and Forge/CEA chain after the plugin/pro hardening work.

## Published in this continuation

Published successfully to crates.io in the final continuation:

- `typed-patch v0.1.0`
- `check-runner-sys v0.1.0`
- `stabilizer-core v0.1.0`
- `check-runner v0.1.0`
- `cea-core v0.1.0`
- `cea-store v0.1.0`
- `cea-sqlite v0.1.0`
- `llm-tool-runtime v0.1.0`
- `forge-engine v0.2.0`
- `assurance-runtime v0.1.0`
- `attestation-exchange v0.1.0`
- `authority-delegation v0.1.0`
- `constitutional-memory v0.1.0`
- `continuity-runtime v0.1.0`
- `effect-runtime v0.1.0`
- `mechanism-runtime v0.1.0`
- `verification-control v0.1.0`
- `verification-policy v0.1.0`
- `verification-calibration v0.1.0`
- `verification-adjudication v0.1.0`
- `forge-pilot v0.1.0`

Previously published in the same top-7 execution thread:

- `ai-batch-queue v0.2.0`
- `comfyui-rs v0.2.0`
- `ollama-vision v0.2.0`
- `effect-signature v0.1.0`
- `forge-policy v0.1.0`
- `mindstate-core v0.1.0`
- `sandbox-workspace v0.1.0`

Total newly published in the top-7 work: 28 crates.

## Verified gates

agent-memory-kits:

- `python -m unittest discover tests/` → 123 tests pass
- `python -m pytest tests/test_pro_plugin_hardening.py -q -o 'addopts='` → 5 pass

Libraries:

- `cargo test -p agent-graph --all-targets` → pass
- `cargo test -p quant-codec-core --all-targets` → pass
- `cargo test -p tauri-queue --all-targets` → pass
- `cargo test -p claim-ledger --all-targets` → pass
- `cargo test -p forge-engine --all-targets` → pass
- `cargo test -p forge-pilot --all-targets` → pass
- `cargo test --manifest-path context-governor/Cargo.toml --all-targets` → pass
- `cargo fmt --manifest-path context-governor/Cargo.toml --check` → pass after formatting
- `cargo clippy --manifest-path context-governor/Cargo.toml --all-targets -- -D warnings` → pass
- `cargo test --manifest-path semantic-memory-mcp/Cargo.toml --all-targets` → pass (15 tests)

## Resolved blockers

### Forge/CEA chain

`forge-engine v0.2.0` and `forge-pilot v0.1.0` are now both published. `forge-pilot` was published with its default `governance` feature intact; no semantics were weakened to force the publish.

### Missing version metadata

Several local path dependencies needed version fields before crates.io would accept dependent crates. Added version metadata to:

- `attestation-exchange` → `stack-ids = 0.1.1`
- `constitutional-memory` → `stack-ids = 0.1.1`
- `effect-runtime` → `stack-ids = 0.1.1` and description metadata
- `mechanism-runtime` → `stack-ids = 0.1.1`
- verification family → `llm-tool-runtime`, `stack-ids`, `semantic-memory-forge`, and verification cross-deps

## Remaining blocker intentionally not chased

### Queue crates

User explicitly said agent/job queue is fine; do not chase this now.

- `job-queue v0.2.0` dry-run passes but crates.io publish is blocked by ownership: the crate exists but this account is not an owner.
- `tauri-queue v0.3.0` tests pass but publish depends on the job-queue ownership decision.

## crates.io rate limits

The registry repeatedly enforced new-crate rate limits (~one new crate per 10-minute window late in the run). Successful publishes were done by waiting for the exact stated window and retrying.
