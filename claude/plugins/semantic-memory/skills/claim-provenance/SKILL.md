---
name: claim-provenance
description: "Use claim-ledger to back material agent assertions with claim/evidence/provenance receipts. Create claims from facts, add evidence, verify integrity, and export bundles for audit."
---

# Claim Provenance

Use claim-ledger when an agent assertion needs a verifiable provenance receipt.

## When to use

- When making a material claim that should be backed by evidence (not just a memory fact)
- When verifying the integrity of a prior ClaimLedger output directory
- When exporting a bundle of claims/evidence for handoff or audit
- When verifying an append-only ledger digest chain for tamper detection

## Tools

- `cl_run` — run the full ClaimLedger pipeline on a directory, producing claims, evidence, and receipts
- `cl_inspect` — inspect a claims JSONL file and return summary statistics
- `cl_validate` — validate a ClaimLedger output directory for integrity and digest chain correctness
- `cl_export_bundle` — export a generic app-agnostic bundle from an output directory
- `cl_ledger_verify` — verify the append-only JSONL ledger digest chain for tamper detection

## Rules

1. A claim with evidence is stronger than a fact without. When an assertion matters, back it.
2. Receipts prove provenance, not task success.
3. Use `cl_validate` before trusting a ClaimLedger output directory.
4. Use `cl_ledger_verify` to detect tampering in the digest chain.
5. Use `cl_export_bundle` when handing off claims to another agent or auditor.
