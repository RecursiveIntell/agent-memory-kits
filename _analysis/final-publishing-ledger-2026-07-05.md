# Final publishing ledger — 2026-07-05

Scope: finish the publishable crates and Forge/CEA/governance/queue chain after the plugin/pro hardening work.

## Published in the final continuation

Published successfully to crates.io:

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
- `agent-queue v0.2.0`
- `tauri-queue v0.3.0`

Previously published in the same top-7 execution thread:

- `ai-batch-queue v0.2.0`
- `comfyui-rs v0.2.0`
- `ollama-vision v0.2.0`
- `effect-signature v0.1.0`
- `forge-policy v0.1.0`
- `mindstate-core v0.1.0`
- `sandbox-workspace v0.1.0`

Total newly published in the top-7 work: 30 crates.

## Queue resolution

The original local crate directory remains `job-queue`, but the package was renamed to `agent-queue` for crates.io because `job-queue` normalizes to the existing `job_queue` crate name on crates.io, which this account does not own.

`tauri-queue` now depends on it as:

```toml
job_queue = { package = "agent-queue", version = "0.2.0", path = "../job-queue" }
```

This preserves the internal Rust import path (`job_queue::...`) while publishing under the available product name `agent-queue`.

## Verified gates

agent-memory-kits:

- `python -m unittest discover tests/` → 123 tests pass
- `python -m pytest tests/test_pro_plugin_hardening.py -q -o 'addopts='` → 5 pass

Libraries:

- `cargo test -p agent-queue --all-targets` → 44 tests pass
- `cargo test -p tauri-queue --all-targets` → pass
- `cargo test -p agent-graph --all-targets` → pass
- `cargo test -p quant-codec-core --all-targets` → pass
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

### Queue chain

`agent-queue v0.2.0` and `tauri-queue v0.3.0` are now both published and visible via `cargo search`.

### Missing version metadata

Several local path dependencies needed version fields before crates.io would accept dependent crates. Added version metadata to queue, Forge, governance, verification, and runtime crates as needed.

## crates.io rate limits

The registry repeatedly enforced new-crate rate limits (~one new crate per 10-minute window late in the run). Successful publishes were done by waiting for the exact stated window and retrying.
