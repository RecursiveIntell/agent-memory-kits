# release gate

Before claiming work is done, run the release gate and keep the receipt.

1. Run `cargo fmt --check` on the workspace.
2. Run `cargo clippy --all-targets -- -D warnings` on the workspace.
3. Run `cargo test --workspace --all-targets` on the workspace.
4. If any check fails, fix and re-run. Do not claim done with failing gates.
5. Store the command outputs as receipts. A claim of completion without gate receipts is not completion.
6. If a check is skipped, state why explicitly. Silent skips are not acceptable.

For semantic-memory-specific work, also run:
- `shared/scripts/doctor-all.py --deep` to verify kit health.
- `shared/scripts/benchmark-retrieval.py` to produce a retrieval quality receipt.
- `shared/scripts/benchmark-context-governor.py --messages 40` to produce a compaction receipt.

Receipts prove what was checked, not that the work is correct. Correctness is proven by tests passing and user verification.
