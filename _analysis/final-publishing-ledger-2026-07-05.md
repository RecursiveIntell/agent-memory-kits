# Final publishing ledger — 2026-07-05

Scope: finish the publishable crates and Forge/CEA/governance/queue/AiDENs chain after the plugin/pro hardening work.

## Final result

All targeted publish work completed.

Newly published across the top-7/topoff work:

- Forge/CEA + governance/runtime + queue chain: 30 crates
- AiDENs workspace + extra kernel/schema deps from this completion pass: 41 crates

Total newly published in this overall run: 71 crates.

## Forge/CEA, governance, runtime, queue chain

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

## AiDENs workspace and dependent closure

Published successfully to crates.io:

- `aidens v0.1.0`
- `aidens-agency-kit v0.1.0`
- `aidens-app-kit v0.1.0`
- `aidens-arbiter-kit v0.1.0`
- `aidens-autonomous v0.1.0`
- `aidens-boundary-kit v0.1.0`
- `aidens-budget-kit v0.1.0`
- `aidens-capability-kit v0.1.0`
- `aidens-cli v0.1.0`
- `aidens-config v0.1.0`
- `aidens-contracts v0.1.0`
- `aidens-daemon-kit v0.1.0`
- `aidens-delegation-kit v0.1.0`
- `aidens-governance-kit v0.1.0`
- `aidens-integration-tests v0.1.0`
- `aidens-kernel-kit v0.1.0`
- `aidens-memory-kit v0.1.0`
- `aidens-memory-tools v0.1.0`
- `aidens-permit-kit v0.1.0`
- `aidens-plan-kit v0.1.0`
- `aidens-profile-coding v0.1.0`
- `aidens-profile-daemon v0.1.0`
- `aidens-profile-desktop v0.1.0`
- `aidens-profile-memory v0.1.0`
- `aidens-profile-research v0.1.0`
- `aidens-provider-kit v0.1.0`
- `aidens-queue-kit v0.1.0`
- `aidens-receipts v0.1.0`
- `aidens-repair-kit v0.1.0`
- `aidens-runner v0.1.0`
- `aidens-schedule-kit v0.1.0`
- `aidens-security-kit v0.1.0`
- `aidens-testkit v0.1.0`
- `aidens-tool-kit v0.1.0`
- `aidens-tui v0.1.0`
- `aidens-wake-kit v0.1.0`
- `boundary-compiler-core v0.1.0`

Additional dependent crates published to complete the AiDENs/kernel/schema closure:

- `federated-settlement v0.1.0`
- `remote-oracle-admission v0.1.0`
- `discovery-portfolio v0.1.0`
- `spec-execution v0.1.0`
- `kernel-conformance v0.1.0`
- `profile-runtime v0.1.0`
- `contract-schema-gen v0.1.0`

## Queue resolution

The original local crate directory remains `job-queue`, but the package was renamed to `agent-queue` for crates.io because `job-queue` normalizes to the existing `job_queue` crate name on crates.io, which this account does not own.

`tauri-queue` now depends on it as:

```toml
job_queue = { package = "agent-queue", version = "0.2.0", path = "../job-queue" }
```

This preserves the internal Rust import path (`job_queue::...`) while publishing under the available product name `agent-queue`.

## Verified gates

agent-memory-kits:

- `python -m unittest discover tests/` → 128 tests pass
- `python -m pytest tests/test_pro_plugin_hardening.py -q -o 'addopts='` → 5 pass

Libraries:

- `cargo test --workspace --all-targets` in `AiDENs/` → pass
- crates.io API visibility audit for AiDENs workspace → 37 / 37 packages visible at their local versions
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

### AiDENs closure

All 37 AiDENs workspace packages are now visible on crates.io. The final blockers were:

- `kernel-conformance` required `discovery-portfolio` and `spec-execution`
- `aidens-cli` required `contract-schema-gen`
- `contract-schema-gen` required `profile-runtime`
- `aidens-integration-tests` required `aidens-cli`

All were published in dependency order.

### Missing version metadata

Several local path dependencies needed version fields before crates.io would accept dependent crates. Added version metadata to queue, Forge, governance, verification, runtime, AiDENs, kernel-conformance, profile-runtime, and contract-schema-gen crates as needed.

## crates.io rate limits

The registry repeatedly enforced new-crate rate limits (~one new crate per 10-minute window late in the run). Successful publishes were done by waiting for the exact stated window and retrying.
