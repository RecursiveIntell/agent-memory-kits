# Forge/CEA demo path

This demo proves the public Forge stack can produce a patch verification receipt without claiming total correctness.

## Goal

Given a repository and a check command, emit a `PatchVerificationReceiptV1` that records:

- sandboxed command execution;
- exit code and output digests;
- git commit;
- trace ID;
- license state when Pro enforcement is enabled;
- Forge/CEA attribution if a real Forge binary is available;
- explicit fallback state when no binary is available.

## Command

```bash
python3 shared/scripts/verify-patch.py \
  --repo /path/to/repo \
  --claim "patch passes the focused test gate" \
  --check-cmd "cargo test -p my-crate --all-targets" \
  --out-dir /tmp/forge-demo-receipts \
  --no-memory
```

By default, `--binary-path auto` checks:

1. `RI_FORGE_BINARY`
2. `~/.cargo/bin/forge-pilot`
3. `~/.cargo/bin/forge-engine`

If none is available, the receipt remains valid but marks attribution unavailable:

```json
{
  "schema": "PatchVerificationReceiptV1",
  "attribution": {
    "available": false,
    "reason": "Forge binary not available"
  },
  "claim_boundary": "Receipt proves command execution and exit code; it does not prove total correctness or untested behavior."
}
```

## Claim boundary

The receipt proves the check command ran in a copied sandbox and records what happened. It does not prove untested behavior, benchmark superiority, compliance, or production readiness.
