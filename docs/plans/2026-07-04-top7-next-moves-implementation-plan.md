# Top 7 Highest-ROI Next Moves Implementation Plan

> For Hermes: implement in order. Use TDD for behavior changes. Public irreversible publishing is attempted only after dry-run passes and credentials are present; if crates.io credentials are absent or a dependency is not yet published, stop at a receipt-backed blocker instead of faking publication.

Goal: convert the current working-but-dirty 114-test plugin/pro stack into a stabilized, committed, license-enforced, workspace-unblocked, dogfooded product path; then prepare/publish the highest-value Rust crates where possible.

Architecture: Treat `agent-memory-kits` as the product/control-plane repo and `Libraries` as the Rust crate workspace. First stabilize the product repo, then unblock the Rust workspace, then enforce Pro licensing, then complete workflow wiring, then dry-run/publish crates in dependency order, then dogfood locally.

Tech stack: Python 3.14 unittest scripts, shell wrappers, JSON plugin manifests, Rust cargo workspaces, crates.io publish/dry-run, local HTTP license server.

## Current evidence baseline

- `/home/sikmindz/Coding/agent-memory-kits`: `python -m unittest discover tests/` => 114 tests pass.
- agent-memory-kits dirty state before this plan: 24 modified tracked files + 85 untracked files.
- `/home/sikmindz/Coding/Libraries`: cargo operations are blocked by `tauri-queue` depending on package `job_queue` while local path crate is `job-queue`.
- `pro/license-server.py` and `pro/license_client.py` exist, but shared Pro scripts do not yet enforce license tokens.
- `shared/scripts/hostile-audit.py` exists/tests pass, but memory-curator skills do not yet mention it.

## Task 1: Stabilize and checkpoint current plugin stack

Objective: preserve the 114-test product stack in logical commits before more feature work.

Files:
- agent-memory-kits working tree.

Steps:
1. Remove generated `__pycache__` artifacts.
2. Run full tests.
3. Inspect diff categories.
4. Commit logical groups where possible:
   - proof/pro scripts and tests
   - plugin manifest/hook integration
   - docs cleanup/plans/analysis
5. If a full clean logical split is unsafe due to many cross-file changes, create one checkpoint commit with a clear message and proof receipt.

Verification:
- `python -m unittest discover tests/` passes.
- `git status --short` is reduced to only intentional out-of-scope work or clean.

## Task 2: Fix Libraries `job_queue` / `job-queue` blocker

Objective: unblock cargo test and publish dry-runs across Libraries.

Files:
- Modify: `/home/sikmindz/Coding/Libraries/tauri-queue/Cargo.toml`
- Possibly modify: `/home/sikmindz/Coding/Libraries/job-queue/Cargo.toml`

Steps:
1. Write/verify failure with `cargo test -p agent-graph --all-targets` and `cargo publish --dry-run -p tauri-queue --allow-dirty`.
2. Change tauri-queue dependency to the canonical local package name:
   `job-queue = { version = "0.2.0", path = "../job-queue" }`
3. Run cargo checks/tests for job-queue and tauri-queue.
4. Run unrelated cargo tests that were previously blocked.

Verification:
- `cargo test -p job-queue --all-targets`
- `cargo test -p tauri-queue --all-targets`
- `cargo test -p agent-graph --all-targets`
- `cargo test -p quant-codec-core --all-targets`

## Task 3: Make Pro license enforcement real

Objective: Pro scripts must require or embed a validated license token when Pro enforcement is enabled.

Files:
- Modify/create: `shared/scripts/license_client.py`
- Modify: `shared/scripts/release-gate-v2.py`
- Modify: `shared/scripts/verify-patch.py`
- Modify: `shared/scripts/forge-admin-mcp.py`
- Modify: `shared/scripts/agent-guard-mcp.py`
- Modify: `shared/scripts/admin-preflight.py`
- Modify: `shared/scripts/authority-delegation.py`
- Create/modify tests: `tests/test_license_enforcement.py`

Policy:
- Default local/free mode remains compatible unless `RI_PRO_ENFORCE=1` or a script is explicitly a Pro-only MCP server.
- Pro-only scripts require a valid token unless `RI_PRO_LICENSE_SKIP=1`; skipped tokens are marked untrusted and must not be accepted by downstream verification as production proof.
- Receipts include `license_token` or `license_state` metadata.

Verification:
- tests for missing license, skip/dev mode, mocked valid token, expired token, and receipt metadata.

## Task 4: Wire hostile-audit into curator workflow

Objective: make the built hostile-audit capability operational in memory-curator workflows.

Files:
- Modify: `hermes/skills/memory-curator/SKILL.md`
- Modify: Claude/Codex memory-curator equivalents if present.
- Create/modify: tests ensuring skill docs mention hostile-audit and fail-open/quarantine semantics.

Policy:
- Use hostile audit before promoting high-risk, public, business, contested, or cross-namespace facts.
- Auditor unavailable => mark audit unavailable; do not mark verified.
- Auditor rejects => quarantine/supersede; do not promote.

Verification:
- unittest/doc test passes.

## Task 5: Publishing sequence prep and publish where safe

Objective: move highest-value crates toward crates.io publication without false completion claims.

Order:
1. `job-queue` 0.2.0 first if dry-run passes and credentials exist.
2. Practical crates: `ai-batch-queue`, `comfyui-rs`, `ollama-vision`, `tauri-queue`.
3. Forge seed crates: `effect-signature`, `forge-policy`, `mindstate-core`; subsequent Forge crates only after dependencies are actually published.

Steps per crate:
1. Run `cargo publish --dry-run -p <crate> --allow-dirty`.
2. If dry-run passes and crates.io token is available, run `cargo publish -p <crate>`.
3. If publish is blocked by credentials or dependency availability, record exact blocker in publishing ledger.

Verification:
- dry-run logs and/or crates.io publication output recorded.

## Task 6: Add tests to published 0-test crates

Objective: remove credibility risk for public crates `agent-graph` and `quant-codec-core`.

Files:
- Create tests under `/home/sikmindz/Coding/Libraries/agent-graph/tests/` or crate-local test modules.
- Create tests under `/home/sikmindz/Coding/Libraries/quant-codec-core/tests/` or crate-local test modules.

Steps:
1. Inspect public APIs.
2. Write minimal smoke tests for constructor/roundtrip/serialization paths.
3. Run package tests.

Verification:
- `cargo test -p agent-graph --all-targets`
- `cargo test -p quant-codec-core --all-targets`

## Task 7: Deploy local Pro license server and dogfood on personal Hermes

Objective: run the license server locally, create a license, configure Hermes, and verify Pro actions produce licensed receipts.

Files:
- `pro/license-server.py`
- `pro/install.py`
- local config: `~/.ri-pro-config.json` or env vars.

Steps:
1. Start license server on localhost with generated secret in a background tracked process.
2. Create a dev/yearly license using admin endpoint or script interface.
3. Configure local Pro client env/config to use localhost server.
4. Run a Pro script with enforcement enabled and verify token appears.
5. Run invalid-token negative test.

Verification:
- License server `/health` OK.
- valid license token in receipt.
- invalid/missing license blocked under `RI_PRO_ENFORCE=1`.

## Final gauntlet

- `cd /home/sikmindz/Coding/agent-memory-kits && python -m unittest discover tests/`
- `python shared/scripts/release-gate-v2.py --claim "Top 7 next moves implemented or blocked with receipts" --cmd "python -m unittest discover tests/" --cwd /home/sikmindz/Coding/agent-memory-kits --no-memory --out-dir /tmp/top7-proof`
- Rust gates listed in Tasks 2 and 6.

## Claim boundary

Safe if completed:
- “The current plugin stack is checkpointed and test-backed.”
- “The Libraries workspace blocker is fixed if the cargo gates pass.”
- “Pro enforcement is real for the named scripts if license tests pass.”
- “Publishing is prepared/done only for crates whose dry-run/publish output is recorded.”

Unsafe:
- Do not claim crates were published unless cargo publish actually succeeded.
- Do not claim Pro enforcement is unremovable; claim receipt-chain enforcement and token validation only.
- Do not claim hostile audit proves truth; it is a second-model check that can support/quarantine claims.
