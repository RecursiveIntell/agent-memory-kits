# semantic-memory for Claude Code

> September 2026: read the [current stack and upgrade guide](../docs/CURRENT_STACK.md)
> for revision-pinned sources, explicit settings, governed-memory behavior and
> unverified native/HTTP integration gates before using older examples below.

> **Tier 0 reference implementation.** Lifecycle hooks (SessionStart / UserPromptSubmit / PreCompact / Stop), a memory-keeper subagent, capture/curator/maintenance/sync skills, and manifest-declared commands — over `semantic-memory-mcp` (profile-based tool counts, run `generate-tool-surface-docs.py` for current) + `context-governor` (13 CLI commands) + `claim-ledger` (5 tools).
> Plugin marketplace path: `semantic-memory@semantic-memory-kit`.

[![Tier 0](https://img.shields.io/badge/tier-0-blueviolet?style=for-the-badge)](#tier--scope)
[![Local-first](https://img.shields.io/badge/storage-local-green?style=for-the-badge)](#)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue?style=for-the-badge)](#)
[![semantic-memory-mcp](https://img.shields.io/crates/v/semantic-memory-mcp?label=semantic-memory-mcp&style=for-the-badge)](https://crates.io/crates/semantic-memory-mcp)
[![context-governor](https://img.shields.io/crates/v/context-governor?label=context-governor&style=for-the-badge)](https://crates.io/crates/context-governor)
[![claim-ledger](https://img.shields.io/crates/v/claim-ledger?label=claim-ledger&style=for-the-badge)](https://crates.io/crates/claim-ledger)

See the [top-level README](../README.md) for the full capability matrix, architecture overview, and Tier 0 vs Tier 1 distinction.

## Tier / scope

Tier 0 host plugin. This kit is the **reference implementation** that Tier 1 hosts (Cursor, Cline, Roo Code, Windsurf, Continue, OpenCode) reuse. The Tier 0 contract: real lifecycle hooks fire on SessionStart, UserPromptSubmit, PreCompact, and Stop, with deterministic fail-open behavior; capture is model-nudged (the model writes with judgment, not auto-dumped); and every claim of completion is backed by a receipt.

## Architecture

![Tier 0 hooked host architecture](../docs/assets/tier0-hooked-architecture.svg)

Hook paths: `claude/plugins/semantic-memory/hooks/`. Script paths: `claude/plugins/semantic-memory/scripts/`. Skill paths: `claude/plugins/semantic-memory/skills/`. All relative to repo root.

## Install

From the repo root:

```text
/plugin marketplace add RecursiveIntell/agent-memory-kits
/plugin install semantic-memory@semantic-memory-kit
/memory-setup
```

Restart Claude Code once so hooks load. `/memory-setup` installs the binary and allowlists tools.

`SEMANTIC_MEMORY_DIR` must name a directory passed to `--memory-dir`, even if
the directory's name ends in `.db`; an existing file at that path is rejected.
The `/memory-setup` command file still describes `SEMANTIC_MEMORY_DIR` as a
database-file path; that legacy wording is stale. Follow
[`docs/CURRENT_STACK.md`](../docs/CURRENT_STACK.md) for the current behavior.

## What you get

### Hook events (4)

`claude/plugins/semantic-memory/hooks/hooks.json` wires four lifecycle events. The PreCompact event runs both capture and context-governor handlers. Every command hook **fails open** — missing binary, timeout, or bad JSON exits 0 and never blocks the prompt.

| Hook | Event | What it does | Fail-open |
|---|---|---|---|
| `memory-primer.sh` | `SessionStart` (startup, resume, clear) | Uses witnessed stdio retrieval and injects project-scoped primer facts as `additionalContext` | yes — 12s timeout |
| `memory-recall.sh` | `UserPromptSubmit` | Uses witnessed stdio retrieval scoped to the active repository, then injects only provenance-complete hits as `additionalContext` | yes — 12s timeout |
| `memory-capture-nudge.sh` | `PreCompact`, `Stop` | Reminds the model to save durable facts / decisions before compaction or ending a turn; skips repeated Stop callbacks | yes — 5s timeout |
| `context-governor-compact.py` | `PreCompact` | Compacts the transcript and writes a receipt | yes — 30s timeout |

`_resolve.sh` is a shared helper, not a hook event.

### Scripts

`claude/plugins/semantic-memory/scripts/` includes MCP wrappers, doctor/benchmark helpers, ingestion, proof/evidence helpers, admin server launchers, and context-governor audit wrappers. Avoid hardcoded script counts here; the script directory is the source of truth.

- `context-governor-mcp.py` — MCP server entry for `context-governor` (4 `cg_*` tools)
- `claim-ledger-mcp.py` — MCP server entry for `claim-ledger` (5 `cl_*` tools)
- `context-governor-compact.py` — deterministic transcript compaction, writes receipt
- `doctor-all.py` — runs all kit doctors and writes a JSON receipt bundle
- `benchmark-retrieval.py` — quality benchmark over warm HTTP
- `benchmark-context-governor.py` — compaction latency / ratio benchmark
- `ingest_codebase.py` — language-agnostic repo ingester
- `evidence-workbench.py`, `proof-packet.py` — proof/evidence packet helpers
- `context-governor-audit.py` — context-governor audit wrapper
- `run-server.sh`, `run-server-admin.sh` — daily and admin semantic-memory launchers

### Commands (2)

- `/memory-setup` — install binary, allowlist tools, write rules (see `claude/plugins/semantic-memory/commands/memory-setup.md`)
- `/memory-ingest <path>` — run `ingest_codebase.py` on a repo path (see `claude/plugins/semantic-memory/commands/memory-ingest.md`)

### Agent (1)

- `memory-keeper.md` — subagent that audits memory health, runs the curator, and re-anchors stale facts

### Skills (9)

Each skill is `claude/plugins/semantic-memory/skills/<name>/SKILL.md`:

| Skill | Purpose |
|---|---|
| `memory-capture` | When and how to save durable facts and decisions |
| `memory-curator` | Reconcile duplicates, supersede stale facts, prune contradicted records |
| `memory-maintenance` | Vacuum, re-embed stale vectors, run `doctor-all` |
| `memory-sync` | Promote facts across namespaces; pair with `ingest_codebase.py` |
| `knowledge-graph-explorer` | Use `sm_topology`, `sm_communities`, `sm_factor_graph` for second-order discovery |
| `release-gate` | Run `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test --workspace` and store receipts |
| `context-compaction` | Drive `context-governor-compact.py` before manual or auto compaction |
| `claim-provenance` | Back material assertions with `cl_run` / `cl_evidence` / `cl_verify` |
| `llm-output-parsing` | Use the `sm_parse_*` tools to handle think blocks, malformed JSON, trailing text |

### MCP tools exposed

The `semantic-memory-mcp` server exposes profile-based tool counts (lean/standard/full/admin). Run `python shared/scripts/generate-tool-surface-docs.py --out /tmp/tool-surface.json` for current counts. See the [top-level "The three MCP companions" section](../README.md#the-three-mcp-companions) for the full breakdown. `context-governor` exposes 13 CLI commands, `claim-ledger` exposes 5.

## Receipts

- Top-level doctor: `shared/scripts/doctor-all.py --deep` (see [top-level Receipts section](../README.md#receipts-and-benchmarks))
- Hook-specific debug log: `export SEMANTIC_MEMORY_HOOK_DEBUG=~/sm-hooks.log`
- Compaction receipts: `~/.local/share/context-governor/receipts/`
- Claim ledger: append-only JSONL at `~/.local/share/claim-ledger/ledger.jsonl` (verify with `cl_ledger_verify`)

This host also has a host-specific `doctor.py` script via `claude/plugins/semantic-memory/scripts/doctor-all.py`.

## Design principles

Claude Code is the reference impl, so its principles are the strictest:

- **Fail-open hooks.** Every hook exits 0 on error. A missing binary never blocks a prompt.
- **Nudged capture, not auto-dump.** The `memory-capture-nudge.sh` hook reminds the model at `PreCompact` and the first `Stop` callback; it never writes on its own.
- **Hook wiring is declarative.** All four lifecycle events are listed in `claude/plugins/semantic-memory/hooks/hooks.json` — the source of truth.

These extend the [top-level Design principles](../README.md#design-principles); they don't replace them.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Hooks don't fire | Restart Claude Code or open `/hooks` once. Config reloads at session start. |
| `memory-recall.sh` silent | Confirm the binary, `SEMANTIC_MEMORY_DIR`, and the repository namespace; the hook intentionally uses witnessed stdio MCP retrieval and fails open on errors. |
| `memory-recall.sh` injects too much | Raise `SM_RECALL_MINTOP` from 0.58 to 0.65. |
| `/memory-setup` fails on `cargo install` | Re-run after `rustup update stable`. |
| Want to inspect hook payloads | `export SEMANTIC_MEMORY_HOOK_DEBUG=~/sm-hooks.log` and tail. |
