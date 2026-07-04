---
name: release-gate
description: "Run cargo fmt/clippy/test and store gate receipts before claiming work done."
---

# Release Gate

Before claiming work is done, run the release gate and keep the receipt.

1. Run `cargo fmt --check` on the workspace.
2. Run `cargo clippy --all-targets -- -D warnings` on the workspace.
3. Run `cargo test --workspace --all-targets` on the workspace.
4. If any check fails, fix and re-run. Do not claim done with failing gates.
5. Store the command outputs as receipts. A claim of completion without gate receipts is not completion.
6. Build a proof packet with `scripts/evidence-workbench.py` (or `shared/scripts/evidence-workbench.py`) that joins command receipts, evidence refs, and a disposition JSON. Do not claim done unless the packet exits 0 with disposition `promote`.
7. If a check is skipped, state why explicitly. Silent skips are not acceptable.

Receipts prove what was checked, not that the work is correct. Correctness is proven by tests passing and user verification.
