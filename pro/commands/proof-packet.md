# /proof-packet

Create a release-gate proof packet that joins command receipts with claim/disposition JSON.

Usage from the agent-memory-kits repo:

```bash
python shared/scripts/proof-packet.py \
  --command-receipt path/to/fmt-receipt.json \
  --command-receipt path/to/test-receipt.json \
  --claim-json path/to/claim.json \
  --disposition-json path/to/disposition.json \
  --out ~/.local/share/semantic-memory-agent-kits/receipts/proof-packet.json
```

Rules:

- The script exits `0` only when the disposition resolves to `promote` and no command receipt reports failure.
- Every input file is embedded with its SHA-256 digest and byte length.
- A packet proves what was checked and what the release gate disposition was; it does not replace live verification.
