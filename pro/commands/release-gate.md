# /release-gate

Run the RecursiveIntell Pro release gate and emit a receipt-backed proof packet.

Use this when the user asks whether a patch/release is ready to promote, or when a claim needs command receipts before it can be trusted.

Suggested invocation from this repo:

```bash
python shared/scripts/release-gate-v2.py \
  --claim "release gates pass" \
  --cmd "python -m pytest -q" \
  --cwd . \
  --risk-class high \
  --out-dir ~/.local/share/semantic-memory-agent-kits/receipts \
  --write-claim-ledger
```

Rules:

- Promotion requires all command receipts to pass.
- Failed commands reject.
- Timeouts quarantine.
- For high/critical risk, proof-debt failures quarantine instead of promoting.
- A proof packet proves only the commands that ran and their captured exit codes; it does not prove untested behavior.
