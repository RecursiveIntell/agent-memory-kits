# RecursiveIntell Pro Plugin

License: LicenseRef-RecursiveIntell-Pro (yearly license, source-available, not freely redistributable)

## What this is

Receipt-backed verification, patch verification, admin preflight, and proof packet pipeline for AI coding agents. This is the Pro companion to the free RecursiveIntell semantic-memory plugin.

## Features

- **Evidence Workbench / Release Gate** — turn command results into proof packets with promote/reject/quarantine adjudication
- **Claim-Ledger MCP** — promote facts to claims only when evidence exists, with support judgment and contradiction tracking
- **Admin Preflight** — block destructive admin operations (delete namespace, re-embed all, release promotion) without confirmation
- **Authority Delegation** — time-bounded capability leases for delegating admin tools to agents
- **Forge/CEA Patch Verification** — verify patches in a sandbox before apply, with causal edit attribution
- **Context-Governor Audit** — audit MCP tool surface for split-instruction risks, screen knowledge conflicts, evaluate retrieval leakage
- **Receipt-Bench Recall Benchmark** — measure recall@k, nDCG@k, MRR with replayable receipts

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

# Install the pro plugin
python install.py
```

## License verification

Every Pro script contacts the license server to get an HMAC-SHA256 signed token. The token is embedded in every receipt. Downstream tools validate the token before trusting receipts. Removing the license check invalidates the entire receipt chain.

Tokens are short-lived (1 hour default) and bound to the machine fingerprint of the first activation. License keys cannot be shared across machines without re-activation.

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