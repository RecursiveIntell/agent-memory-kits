# RecursiveIntell Pro Plugin

License: LicenseRef-RecursiveIntell-Pro (yearly license, source-available, not freely redistributable)

## What this is

Receipt-backed verification, patch verification, admin preflight, and proof packet pipeline for AI coding agents. This is the Pro companion to the free RecursiveIntell semantic-memory plugin.

## Features

- **Evidence Workbench / Release Gate** — turn command results into proof packets with promote/reject/quarantine adjudication
- **Claim-Ledger MCP** — promote facts to claims only when evidence exists, with support judgment and contradiction tracking
- **Admin Preflight** — emit an effect intent only after the helper receives confirmation for high/critical operations (delete namespace, re-embed all, release promotion); callers must enforce this preflight before invoking the native operation
- **Authority Delegation** — create and inspect time-bounded local JSON lease records; these records do not mint a native authority permit or grant access to an admin tool
- **Forge/CEA Patch Verification** — run an operator-supplied check command in a temporary repository copy and emit a verification receipt, with optional Forge attribution; the copy is not an OS security sandbox
- **Context-Governor Audit** — audit MCP tool surface for split-instruction risks, screen knowledge conflicts, evaluate retrieval leakage
- **Receipt-Bench Recall Benchmark** — measure fixture-based recall@k, nDCG@k and MRR in an `SMBenchmarkReport`; a metric receipt does not establish complete replay

## Requirements

- The free RecursiveIntell semantic-memory plugin must be installed first
- A valid RecursiveIntell Pro license key (contact sales@recursiveintell.com)
- Python 3.10+
- The semantic-memory-mcp and context-governor binaries from the free plugin

## Installation

```bash
# Set your license key
export RI_PRO_LICENSE_KEY="RI-PRO-XXXXXXXXXXXXXXXXXXXX"

# Set the license server (default: https://license.recursiveintell.com)
export RI_PRO_LICENSE_SERVER="https://license.recursiveintell.com"

# From the agent-memory-kits repository root, install the Pro overlay
python3 pro/install.py
```

## License verification

The installer requires a license token.  Receipt-aware helpers use `RecursiveIntellProLicenseStateV1`: enforcement is enabled with `RI_PRO_ENFORCE=1`, while unenforced and explicit development-skip states are marked untrusted.  When enforcement is enabled, a current cached token with the required features is reused; the client contacts `/verify-license` when it needs a token.  A missing token blocks an enforced helper.

The [license server](license-server.py) issues HMAC-SHA256 signed tokens and exposes `/validate-token` for signature and expiry validation.  The [bundled client](license_client.py) checks expiry and required feature membership, but does not independently verify the HMAC signature or call `/validate-token`.  Its `trusted` field is a client-side state label, not a cryptographic validation receipt.  Consumers must verify tokens through an appropriate trusted server boundary before using them as production trust evidence.

Server-issued tokens have a configurable TTL (1 hour by default).  The server locks a license to its first activation fingerprint and checks later activations against that fingerprint.  The local cached-token path does not independently re-check that machine binding.

## Business / managed systems

Yearly license includes:
- All Pro features
- License server access
- Email support

Managed setup option:
- We install and configure the full stack (free + Pro) on your infrastructure
- Custom license server deployment (on-premise or hosted)
- Integration with your CI/CD for release gates
- Priority support

Contact sales@recursiveintell.com for pricing.
