# claim-ledger: claim/evidence/provenance receipts

Use ClaimLedger when an agent assertion needs a verifiable provenance receipt.

When to use:

1. When making a material claim that should be backed by evidence (not just a memory fact).
2. When verifying the integrity of a prior ClaimLedger output directory.
3. When exporting a bundle of claims/evidence for handoff or audit.
4. When verifying an append-only ledger digest chain for tamper detection.

If ClaimLedger MCP tools are available, use:
- `cl_run` to process a directory and produce claims, evidence, and receipts;
- `cl_inspect` to inspect a claims JSONL file;
- `cl_validate` to validate a ClaimLedger output directory;
- `cl_export_bundle` to export a generic app-agnostic bundle;
- `cl_ledger_verify` to verify the append-only JSONL ledger digest chain.

Receipts prove provenance, not task success. A claim with evidence is stronger than a fact without.
