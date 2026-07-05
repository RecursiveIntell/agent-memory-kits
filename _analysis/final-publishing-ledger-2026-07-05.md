# Final publishing ledger — 2026-07-05

Scope: finish the publishable non-queue crates and Forge/CEA chain after the plugin/pro hardening work.

## Published in this continuation

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

Previously published in the same top-7 execution thread:

- `ai-batch-queue v0.2.0`
- `comfyui-rs v0.2.0`
- `ollama-vision v0.2.0`
- `effect-signature v0.1.0`
- `forge-policy v0.1.0`
- `mindstate-core v0.1.0`
- `sandbox-workspace v0.1.0`

Total newly published in the top-7 work: 16 crates.

## Verified gates

agent-memory-kits:

- `python -m unittest discover tests/` → 121 tests pass
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

## Remaining blockers

### Queue crates

User explicitly said agent/job queue is fine; do not chase this now.

- `job-queue v0.2.0` dry-run passes but crates.io publish is blocked by ownership: the crate exists but this account is not an owner.
- `tauri-queue v0.3.0` tests pass but publish depends on the job-queue ownership decision.

### forge-pilot

`forge-engine v0.2.0` is now published.

`forge-pilot v0.1.0` is not published. It is publish-hygienic in the sense that all local path dependencies now include version requirements, but default features include the governance stack. Publishing without changing semantics requires upstream publication of a larger runtime family, beginning with:

- `assurance-runtime v0.1.0` (dry-run passes)
- `attestation-exchange v0.1.0`
- `authority-delegation v0.1.0`
- `constitutional-memory v0.1.0`
- `continuity-runtime v0.1.0`
- `effect-runtime v0.1.0`
- `mechanism-runtime v0.1.0`
- plus non-optional kernel/verification/knowledge crates used by forge-pilot.

I did not change `forge-pilot` default features to avoid reopening its architecture or weakening its declared governance surface just to force a crates.io publish.

### crates.io rate limits

The registry repeatedly enforced new-crate rate limits. Successful publishes were done by waiting for the stated windows and retrying. Continuing through the full forge-pilot upstream graph would be a multi-hour publish sequence, not appropriate to hide as a quick finish.
