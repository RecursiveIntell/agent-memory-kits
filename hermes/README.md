# semantic-memory for Hermes Agent

> **Tier 0 reference implementation.** Manifest-driven skills, hooks, commands, MCP companions, proof helpers, and a memory-keeper subagent — over `semantic-memory-mcp` + `context-governor` + `claim-ledger`. Installs locally (no marketplace).

[![Tier 0](https://img.shields.io/badge/tier-0-blueviolet?style=for-the-badge)](#tier--scope)
[![Local-first](https://img.shields.io/badge/data-100%25%20local-green?style=for-the-badge)](#)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue?style=for-the-badge)](#)
[![semantic-memory-mcp](https://img.shields.io/crates/v/semantic-memory-mcp?label=semantic-memory-mcp&style=for-the-badge)](https://crates.io/crates/semantic-memory-mcp)
[![context-governor](https://img.shields.io/crates/v/context-governor?label=context-governor&style=for-the-badge)](https://crates.io/crates/context-governor)
[![claim-ledger](https://img.shields.io/crates/v/claim-ledger?label=claim-ledger&style=for-the-badge)](https://crates.io/crates/claim-ledger)

See the [top-level README](../../README.md) for the full capability matrix, architecture overview, and Tier 0 vs Tier 1 distinction.

## Tier / scope

Tier 0 host plugin. This kit is the **reference implementation** for Hermes Agent. The Tier 0 contract is the same as Claude/Codex: real lifecycle hooks (here, `on_session_start`, `pre_llm_call`, `post_tool_use`, `post_llm_call`) plus manifest-declared skills, commands, MCP companions, proof helpers, and the memory-keeper subagent. Hermes is installed by `cp -r`-ing the skills/agents/scripts directories into `~/.hermes/`; there is no marketplace path.

## Architecture

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart LR
    HE["Hermes Agent<br/>(skills/agents/commands)"] --> SK["skills/<br/>9 SKILL.md"]
    HE --> AG["agents/<br/>memory-keeper.md"]
    HE --> CM["commands/<br/>/memory-setup · /memory-ingest"]
    HE --> PJ["plugin.json<br/>(manifest)"]
    SK --> MCP["semantic-memory-mcp<br/>(warm HTTP :1738)"]
    AG --> MCP
    CM --> MCP
    MCP --> CG["context-governor<br/>MCP"]
    MCP --> CL["claim-ledger<br/>MCP"]
    MCP --> DB[("SQLite + FTS5 + HNSW")]
    CG --> RS[("Receipt store")]
    CL --> LR[("Claim/evidence ledger")]
```

Skill paths: `hermes/skills/`. Agent path: `hermes/agents/`. Command paths: `hermes/commands/`. Manifest: `hermes/plugin.json`.

## Install

Keep the canonical kit layout available to the hook process; the Hermes hooks
load the shared fail-closed framing module from that root. Set
`SEMANTIC_MEMORY_KIT_ROOT` to this checkout (or deploy the complete checkout
with `hermes/` and `shared/` as siblings), then register the manifest at
`hermes/plugin.json`. Do not deploy only the skills/agents/scripts directories:
that omits the lifecycle hooks and their shared provenance gate.

For hosts that use the canonical checkout directly:

```bash
export SEMANTIC_MEMORY_KIT_ROOT="$PWD"
# Register/load ./hermes/plugin.json using Hermes's plugin configuration.
```

Restart Hermes so the new skills/agents/commands are picked up.

## What you get

### Skills (9)

`hermes/skills/<name>/SKILL.md`:

| Skill | Purpose |
|---|---|
| `memory-capture` | When and how to save durable facts and decisions |
| `memory-curator` | Reconcile duplicates, supersede stale, prune contradicted |
| `memory-maintenance` | Vacuum, re-embed stale vectors, run `doctor-all` |
| `memory-sync` | Promote facts across namespaces; pair with `ingest_codebase.py` |
| `knowledge-graph-explorer` | Use `sm_topology`, `sm_communities`, `sm_factor_graph` for second-order discovery |
| `release-gate` | Run `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test --workspace` and store receipts |
| `context-compaction` | Drive `context-governor-compact.py` before manual or auto compaction |
| `claim-provenance` | Back material assertions with `cl_run` / `cl_evidence` / `cl_verify` |
| `llm-output-parsing` | Use the `sm_parse_*` tools to handle think blocks, malformed JSON, trailing text |

### Agent (1)

- `agents/memory-keeper.md` — subagent that audits memory health, runs the curator, and re-anchors stale facts

### Commands

Declared in `hermes/plugin.json`:

- `/memory-setup` — install binary, allowlist tools, write rules (see `hermes/commands/memory-setup.md`)
- `/memory-ingest <path>` — run `ingest_codebase.py` on a repo path (see `hermes/commands/memory-ingest.md`)
- `/memory-gaps` — inspect semantic-memory coverage gaps (see `hermes/commands/memory-gaps.md`)
- `/evidence-workbench` — create evidence/proof packets from command output (see `hermes/commands/evidence-workbench.md`)
- `/proof-packet` — join receipts into an adjudicated proof packet (see `hermes/commands/proof-packet.md`)

### Scripts

`hermes/scripts/` includes MCP wrappers, doctor/benchmark helpers, ingestion, proof/evidence helpers, admin server launchers, context-governor audit wrappers, and Forge admin wiring. Treat `hermes/plugin.json` plus the script directory as source of truth instead of hardcoding script counts in docs.

Key entries:

- `context-governor-mcp.py` — MCP server entry for `context-governor`
- `claim-ledger-mcp.py` — MCP server entry for `claim-ledger`
- `context-governor-compact.py` — deterministic transcript compaction
- `context-governor-audit.py` — audit wrapper for context-governor high-ROI checks
- `doctor-all.py` — runs all kit doctors and writes a JSON receipt bundle
- `benchmark-retrieval.py` — quality benchmark over warm HTTP
- `benchmark-context-governor.py` — compaction latency / ratio benchmark
- `ingest_codebase.py` — language-agnostic repo ingester
- `evidence-workbench.py`, `proof-packet.py` — proof/evidence packet helpers
- `run-server.sh`, `run-server-admin.sh` — daily and admin semantic-memory launchers
- `forge-admin-mcp.py` — admin-only patch verification MCP wrapper

### Plugin manifest

`hermes/plugin.json` declares skills, the memory-keeper agent, 4 hook events (`on_session_start`, `pre_llm_call`, `post_tool_use`, `post_llm_call`), commands, and MCP servers for semantic memory, context-governor, claim-ledger, admin semantic-memory, and Forge admin patch verification. Hermes reads this manifest at startup.

### MCP tools exposed

`semantic-memory-mcp` tool counts vary by profile (lean/standard/full/admin). Run `python shared/scripts/generate-tool-surface-docs.py --out /tmp/tool-surface.json` for current counts. `context-governor` exposes 13 CLI commands. `claim-ledger` exposes 5 tools. See the [top-level "The three MCP companions" section](../../README.md#the-three-mcp-companions).

Hermes uses warm HTTP port `1738` by default (the manifest passes `--http-port 1738` to `run-server.sh`).

## Receipts

- Top-level doctor: `shared/scripts/doctor-all.py --deep`
- Host-specific doctor: `hermes/scripts/doctor-all.py`
- Hook debug log: `export SEMANTIC_MEMORY_HOOK_DEBUG=~/sm-hooks.log`
- Compaction receipts: `~/.local/share/context-governor/receipts/`
- Claim ledger: append-only JSONL at `~/.local/share/claim-ledger/ledger.jsonl`
- Admin/full MCP profile: use the `semantic-memory-admin` server entry (or run `hermes/scripts/run-server-admin.sh`) for maintenance tools hidden by the daily lean profile.
- Release-gate proof packets: run `hermes/scripts/proof-packet.py` or `shared/scripts/proof-packet.py` to join command receipts with claim/disposition JSON; only disposition `promote` exits 0.

This host has no host-specific `doctor.py` separate from `doctor-all.py`.

## Design principles

Hermes is the third reference impl, focused on minimal installation friction:

- **File install, not marketplace.** `cp -r` is the only install step. No marketplace, no auth flow, no plugin server.
- **One manifest, one set of skills.** `hermes/plugin.json` is the single source of truth for what Hermes should load.
- **Warm port `1738` by default.** Hermes runs the warm sidecar on `1738`; Codex and Claude use `1739`; this avoids cross-agent port collisions when more than one agent runs locally.

These extend the [top-level Design principles](../../README.md#design-principles); they don't replace them.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Skills not picked up | Confirm `~/.hermes/skills/<skill>/SKILL.md` exists; restart Hermes. |
| Agent not registered | Confirm `~/.hermes/agents/memory-keeper.md` exists; restart Hermes. |
| Warm port conflict with Codex/Claude | Hermes uses `1738`. Codex/Claude use `1739`. Set `SEMANTIC_MEMORY_HTTP_PORT=0` to disable the warm server on this host. |
| Hook silent | `export SEMANTIC_MEMORY_HOOK_DEBUG=~/sm-hooks.log` and tail. |
| `cargo install` fails | Re-run after `rustup update stable`. |
