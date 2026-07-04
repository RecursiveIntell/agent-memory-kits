# /verify-patch

Verify a patch in a sandbox and emit a `PatchVerificationReceiptV1`.

Use this before applying or promoting risky code changes, especially when the claim is about correctness, safety, or release readiness.

Suggested invocation from this repo:

```bash
python shared/scripts/verify-patch.py \
  --repo . \
  --claim "patch passes focused verification" \
  --check-cmd "python -m pytest tests/test_target.py -q" \
  --out-dir ~/.local/share/semantic-memory-agent-kits/receipts
```

Rules:

- The repo is copied into a temp sandbox before checks run.
- The check command is operator-supplied and recorded in the receipt.
- Semantic-memory writes use `SEMANTIC_MEMORY_HTTP_URL` or `SEMANTIC_MEMORY_HTTP_PORT`; they do not assume a hardcoded port.
- The receipt proves command execution and exit code only, not total correctness.
