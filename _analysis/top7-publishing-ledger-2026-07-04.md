# Top 7 publishing ledger — 2026-07-04

## Published successfully

- `ai-batch-queue v0.2.0` — published to crates.io. Log: `/tmp/top7-publish-logs/ai-batch-queue.publish.log`
- `comfyui-rs v0.2.0` — published to crates.io. Log: `/tmp/top7-publish-logs/comfyui-rs.publish.log`
- `ollama-vision v0.2.0` — published to crates.io. Log: `/tmp/top7-publish-logs/ollama-vision.publish.log`
- `effect-signature v0.1.0` — published to crates.io. Log: `/tmp/top7-publish-logs/effect-signature.publish.log`
- `forge-policy v0.1.0` — published to crates.io. Log: `/tmp/top7-publish-logs/forge-policy.publish.log`
- `mindstate-core v0.1.0` — published to crates.io after rate-limit cooldown. Log: `/tmp/top7-publish-logs/mindstate-core.publish2.log`

## Dry-run passed but publish blocked/deferred

- `sandbox-workspace v0.1.0` — dry-run passed after `forge-policy` publish. Actual publish blocked by crates.io rate limit until 2026-07-04T23:39:34Z. Log: `/tmp/top7-publish-logs/sandbox-workspace.dryrun.log`, `/tmp/top7-publish-logs/sandbox-workspace.publish.log`.

## Blocked

- `job-queue v0.2.0` — dry-run passes after adding `stack-ids = "0.1.1"` and shortening keyword `background-processing` to `background`; actual publish blocked by crates.io ownership: `this crate exists but you don't seem to be an owner`. Log: `/tmp/top7-publish-logs/job-queue.publish2.log`.
- `tauri-queue v0.3.0` — remains blocked because it depends on `job-queue v0.2.0`, which cannot be published under current ownership. Log: `/tmp/top7-publish-logs/tauri-queue.dryrun.log`.

## Not attempted yet because dependency chain/rate limit

- `typed-patch`, `stabilizer-core`, `check-runner`, `cea-core`, `cea-store`, `cea-sqlite`, `forge-engine`, `forge-pilot` — resume after `sandbox-workspace` is published and available on crates.io.

## Required next decision

`job-queue` name conflict needs an owner/name decision:

1. Accept crates.io owner invite for existing `job-queue`, then publish 0.2.0.
2. Rename public crate to a RecursiveIntell-scoped name (for example `ri-job-queue`) and update dependents.
3. Use the existing crates.io `job_queue` crate only if API-compatible (not verified; unsafe to assume).
