# Semantic Memory Agent Plugin Expansion Plan

> For Hermes/Codex/Claude implementers: this is a product + implementation plan for expanding semantic-memory-agent-kits beyond Claude Code, Codex CLI, and Hermes Agent.

Goal: make semantic-memory-mcp easy to install and use from the other popular AI coding agents/editors without rebuilding the memory server per host.

Architecture: keep semantic-memory-mcp as the one shared substrate. Build thin host adapters that do only four things: install/register MCP, start or point at a warm HTTP sidecar, add prompt/session recall where the host exposes hooks, and ship host-native commands/docs. Do not fork the memory semantics per agent.

Evidence basis checked 2026-07-02:
- Current repo: /home/sikmindz/Coding/semantic-memory-claude-kit
- Existing packages: claude/, codex/, hermes/
- Current README advertises only Claude Code, Hermes Agent, and Codex CLI.
- Live docs probed for MCP support: Cursor, Windsurf, Continue, OpenCode, Roo Code, Cline.
- Existing validated installs: Claude semantic-memory@semantic-memory-kit 0.6.0; Codex semantic-memory@personal 0.7.0+codex.20260627.

Non-goals:
- Do not build a new memory server.
- Do not require cloud services.
- Do not claim every host supports automatic pre-prompt recall. Some hosts only support MCP tools/config.
- Do not ship private Josh-specific paths as defaults.

---

## 1. Host tiers

### Tier 0 — already done / maintain

| Host | Status | Package path | Capability |
|---|---|---|---|
| Claude Code | Done | claude/plugins/semantic-memory | MCP + hooks + commands + skills/agents |
| Codex CLI | Done | codex/plugins/semantic-memory | MCP + global/project hooks + skills/prompts + codebase ingest |
| Hermes Agent | Done-ish | hermes/ | MCP/hooks/skills layout, but docs and install path need cleanup |

Maintenance rule: keep these three as reference implementations. Every new host should reuse the same shared scripts where possible.

### Tier 1 — highest ROI next plugins

These hosts have broad usage and either native MCP support or a simple MCP config surface.

| Host | Why | Expected integration level | Package path to add |
|---|---|---|---|
| Cursor | Very popular AI IDE; supports MCP config | MCP-first + optional install script; likely no true pre-prompt hook | cursor/ |
| Windsurf | Popular coding-agent IDE; supports Cascade MCP | MCP-first + docs/install script | windsurf/ |
| Cline | Popular VS Code agent; MCP is central to product | MCP-first + command docs | cline/ |
| Roo Code | Cline-derived, popular power-user fork; MCP support | MCP-first + command docs | roo-code/ |
| Continue | Open-source IDE assistant; supports MCP | MCP-first + config snippets | continue/ |
| OpenCode | Popular terminal coding agent; supports MCP servers | MCP-first + config snippets; investigate plugin/custom command surface | opencode/ |

Tier 1 public promise: "semantic-memory tools available inside the agent via MCP, plus a one-command setup/doctor path." Only claim auto-recall when the host has a hook/event system that can inject context before model calls.

### Tier 2 — useful but different packaging model

| Host | Why | Expected integration level | Notes |
|---|---|---|---|
| Gemini CLI | Popular Google terminal agent; extension system needs current docs verification | extension or config package | Check latest docs before building; prior URL moved/404ed. |
| Goose | MCP/extensions ecosystem; useful for local-first workflows | extension recipe | Need current docs path; prior docs URL moved/404ed. |
| Aider | Popular terminal coding agent, but not plugin-first | config + wrapper scripts | Likely MCP/config recipe, not first-class plugin. |
| OpenHands | Popular autonomous coding platform | container/env config + MCP recipe | Treat as deployment recipe. |
| Zed Agent Panel | growing editor agent; MCP support may vary by version | config recipe | Verify current extension surface. |

Tier 2 public promise: "integration recipes" unless a real host-native plugin/extension package exists.

---

## 2. Adapter classes

### Class A — MCP-only adapters

Use when the host can register an MCP server but has no reliable lifecycle hooks.

Deliverables per host:
- README.md with install and verification.
- mcp config snippet pointing to `semantic-memory-mcp` or bundled `scripts/run-server.sh`.
- setup.sh that installs semantic-memory-mcp if missing.
- doctor.sh or Python doctor wrapper that confirms:
  - binary exists;
  - memory dir exists;
  - MCP command starts and lists tools if host supports testing;
  - warm HTTP sidecar health if configured.

Capabilities:
- Manual/agent-invoked `sm_search`, `sm_add_fact`, graph, provenance, claims.
- No automatic prompt recall unless host supports prompt hooks.

Hosts: Cursor, Windsurf, Continue, OpenCode first pass, Cline/Roo first pass.

### Class B — Hooked adapters

Use when host exposes pre-prompt/session-start/pre-compact hooks or extension APIs that can inject context.

Deliverables per host:
- Everything in Class A.
- memory-primer hook.
- memory-recall hook.
- capture nudge hook.
- host-native command(s): memory setup, memory ingest, memory doctor.

Capabilities:
- Automatic relevant recall.
- Project-scoped primer.
- Capture nudges.

Hosts: Claude Code and Codex already. Future: OpenCode or Gemini CLI only if verified.

### Class C — Recipe-only adapters

Use when host has no plugin system or the integration would be brittle.

Deliverables:
- docs/<host>.md
- copy-paste config snippets.
- explicit capability boundary.

Hosts: Aider, OpenHands, Zed until proven otherwise.

---

## 3. Shared core refactor before new host work

Current duplication risk: claude/, codex/, and hermes/ each carry similar run-server, ingest, and setup logic. Before adding 6 more hosts, extract host-agnostic pieces.

Create:

```text
shared/
  scripts/
    find_semantic_memory_binary.py
    install_semantic_memory_mcp.sh
    run-server.sh
    doctor_core.py
    ingest_codebase.py
  snippets/
    mcp-stdio.json
    mcp-http.json
  docs/
    capability-boundaries.md
    troubleshooting.md
```

Rules:
- Host packages may copy shared files at release time, but source of truth lives in shared/.
- Shared scripts must not contain Josh-specific paths.
- Default memory dir: `${SEMANTIC_MEMORY_DIR:-$HOME/.local/share/semantic-memory}` for public packages.
- Josh/Hermes local memory dir remains local config, not public default.
- Each host package has a `scripts/doctor.*` that imports or shells out to shared doctor logic.

---

## 4. Repository layout target

```text
semantic-memory-agent-kits/
  README.md
  shared/
    scripts/
    snippets/
    docs/
  claude/
  codex/
  hermes/
  cursor/
    README.md
    mcp.json.example
    scripts/setup.sh
    scripts/doctor.py
  windsurf/
    README.md
    mcp_config.json.example
    scripts/setup.sh
    scripts/doctor.py
  cline/
    README.md
    mcp_settings.json.example
    scripts/setup.sh
    scripts/doctor.py
  roo-code/
    README.md
    mcp_settings.json.example
    scripts/setup.sh
    scripts/doctor.py
  continue/
    README.md
    config.yaml.example
    scripts/setup.sh
    scripts/doctor.py
  opencode/
    README.md
    opencode.json.example
    scripts/setup.sh
    scripts/doctor.py
  recipes/
    aider.md
    goose.md
    gemini-cli.md
    openhands.md
    zed.md
```

---

## 5. Host-by-host implementation tasks

### Phase 0 — source cleanup and shared core

Acceptance gate:
- Existing Claude plugin still validates.
- Existing Codex plugin Python hooks compile.
- `diff -qr` shows Codex installed source matches `codex/plugins/semantic-memory` except caches.

Tasks:
1. Create `shared/scripts/run-server.sh` by generalizing Codex run-server.
2. Create `shared/scripts/install_semantic_memory_mcp.sh` from Codex setup binary discovery.
3. Create `shared/scripts/doctor_core.py` with binary/memory-dir/HTTP health checks.
4. Move/copy language-agnostic ingester to `shared/scripts/ingest_codebase.py`.
5. Patch Claude/Codex/Hermes package scripts to use shared source or explicitly document generated copies.
6. Add a release checklist that validates every host package.

### Phase 1 — Cursor package

Files:
- Create: `cursor/README.md`
- Create: `cursor/mcp.json.example`
- Create: `cursor/scripts/setup.sh`
- Create: `cursor/scripts/doctor.py`

Expected config shape to verify against current Cursor docs before finalizing:
```json
{
  "mcpServers": {
    "semantic-memory": {
      "command": "semantic-memory-mcp",
      "args": ["--memory-dir", "$HOME/.local/share/semantic-memory", "--tool-profile", "lean"]
    }
  }
}
```

Acceptance gate:
- Cursor docs path checked live.
- Example JSON parses.
- Doctor confirms binary and can run `semantic-memory-mcp --help`.
- README clearly says this is MCP tools, not automatic prompt recall, unless Cursor hook support is verified.

### Phase 2 — Windsurf package

Files:
- Create: `windsurf/README.md`
- Create: `windsurf/mcp_config.json.example`
- Create: `windsurf/scripts/setup.sh`
- Create: `windsurf/scripts/doctor.py`

Acceptance gate:
- Windsurf Cascade MCP docs checked live.
- Example JSON parses.
- README states capability boundary.

### Phase 3 — Cline and Roo Code packages

Files:
- Create: `cline/README.md`
- Create: `cline/mcp_settings.json.example`
- Create: `cline/scripts/setup.sh`
- Create: `cline/scripts/doctor.py`
- Create: `roo-code/README.md`
- Create: `roo-code/mcp_settings.json.example`
- Create: `roo-code/scripts/setup.sh`
- Create: `roo-code/scripts/doctor.py`

Acceptance gate:
- Current Cline and Roo docs checked live.
- Confirm their settings file names/locations before publishing.
- JSON examples parse.
- Doctor can validate binary and memory dir.

### Phase 4 — Continue package

Files:
- Create: `continue/README.md`
- Create: `continue/config.yaml.example` or equivalent current config format.
- Create: `continue/scripts/setup.sh`
- Create: `continue/scripts/doctor.py`

Acceptance gate:
- Continue MCP docs checked live.
- YAML/JSON example parses.
- Capability boundary stated.

### Phase 5 — OpenCode package

Files:
- Create: `opencode/README.md`
- Create: `opencode/opencode.json.example` or equivalent current config format.
- Create: `opencode/scripts/setup.sh`
- Create: `opencode/scripts/doctor.py`

Acceptance gate:
- OpenCode MCP docs checked live.
- Config example parses.
- If OpenCode supports commands/hooks, add a follow-up task for Class B upgrade. Otherwise keep MCP-only.

### Phase 6 — recipe docs for Tier 2

Files:
- Create: `recipes/aider.md`
- Create: `recipes/gemini-cli.md`
- Create: `recipes/goose.md`
- Create: `recipes/openhands.md`
- Create: `recipes/zed.md`

Acceptance gate:
- Every recipe states source docs checked date.
- Every recipe has copy-paste setup commands.
- Every recipe has explicit "what works / what does not".

---

## 6. Public README rewrite

Patch root README after Phase 1 starts.

New positioning:

> Semantic Memory Agent Kits gives popular AI coding agents a shared, local-first persistent memory through semantic-memory-mcp. First-class plugins exist for Claude Code, Codex CLI, and Hermes Agent; MCP setup kits exist for Cursor, Windsurf, Cline, Roo Code, Continue, and OpenCode.

Add capability table:

| Host | MCP tools | Auto recall | Project primer | Codebase ingest | Status |
|---|---:|---:|---:|---:|---|
| Claude Code | yes | yes | yes | yes | stable |
| Codex CLI | yes | yes | yes | yes | stable |
| Hermes Agent | yes | yes | yes | yes | local stable |
| Cursor | planned | no/unknown | no/unknown | manual | next |
| Windsurf | planned | no/unknown | no/unknown | manual | next |
| Cline | planned | no/unknown | no/unknown | manual | next |
| Roo Code | planned | no/unknown | no/unknown | manual | next |
| Continue | planned | no/unknown | no/unknown | manual | next |
| OpenCode | planned | investigate | investigate | manual | next |

Claim boundary:
- "MCP tools" means the agent can call semantic-memory tools.
- "Auto recall" means the host injects relevant memory into model context before answering.
- Do not blur those two.

---

## 7. Test matrix

Add a release script:

```text
scripts/validate-all-kits.sh
```

Checks:
- JSON manifests parse.
- YAML examples parse if Python yaml available, otherwise syntax smoke.
- Shell scripts pass `bash -n`.
- Python scripts pass `python3 -m py_compile`.
- Claude plugin validates with `claude plugin validate` when claude is installed.
- Codex plugin list/add smoke when codex is installed.
- `semantic-memory-mcp --help` contains flags used by examples, or examples guard optional flags.

---

## 8. Release strategy

1. Keep one monorepo: `semantic-memory-agent-kits`.
2. Tag releases as `v0.8.0` etc for the kit, while host plugin versions may include host suffixes.
3. Generate per-host zip/tar artifacts under `dist/`.
4. Root README leads with stable hosts, then MCP kits.
5. Each host README has a 60-second install path and a doctor command.

Recommended versioning:
- 0.8.0: shared core + Cursor/Windsurf/Cline/Roo/Continue/OpenCode MCP kits.
- 0.8.1: docs fixes from first users.
- 0.9.0: any host upgraded from MCP-only to hooked auto-recall.

---

## 9. Highest ROI build order

1. Shared core extraction.
2. Cursor package.
3. Cline + Roo package pair.
4. Windsurf package.
5. Continue package.
6. OpenCode package.
7. Tier 2 recipes.
8. Root README rewrite and diagrams.

Reason: Cursor/Cline/Roo/Windsurf are the most likely adoption surfaces for users who already understand MCP. Continue/OpenCode matter, but their audiences are smaller or more likely to tolerate manual config.

---

## 10. Immediate next action

Create Phase 0 shared core and the Cursor MCP-only kit first. That produces the reusable pattern for the rest.

Minimum shippable PR:
- `shared/scripts/run-server.sh`
- `shared/scripts/doctor_core.py`
- `cursor/README.md`
- `cursor/mcp.json.example`
- `cursor/scripts/setup.sh`
- `cursor/scripts/doctor.py`
- root README capability table update
- `scripts/validate-all-kits.sh`

Do not start by building six bespoke packages. Build one shared core + one host, verify it, then clone the pattern.


## Context-injection pass shipped

Added a host-neutral context injector and rule installer:

- `shared/scripts/semantic-memory-context.py`: prompt in, compact recall block out; warm HTTP first, stdio MCP fallback.
- `shared/rules/semantic-memory-context.md`: common rule semantics for agents without direct hooks.
- `shared/scripts/install-context-rules.py`: host-specific rule/instruction installer for Cursor, Windsurf, Cline, Roo Code, Continue, and OpenCode.

This intentionally separates two capability tiers:

1. Hook tier: Claude Code and Codex can inject recall at prompt/session lifecycle events.
2. Rule/context tier: MCP-only agents get automatic behavioral guidance through their rule systems and a deterministic context command; no false claim of a hidden pre-prompt hook.


## Context Governor companion pass

Added context-governor as a companion for all MCP kits:

- shared MCP server exposing receipt list/search/expand/diff tools.
- shared compact command for exported transcript JSON.
- host rule installer now injects semantic-memory recall guidance and context-governor compaction guidance together.
- JSON MCP examples include both `semantic-memory` and `context-governor`.

Boundary: for non-hook hosts, compaction is rule/command/MCP assisted, not automatic pre-compact transcript interception.

## Low-effort/high-ROI polish pass

Added the adoption and receipts layer:

- `shared/scripts/doctor-all.py --deep`: runs shared + per-host doctors and writes JSON receipt bundles under `~/.local/share/semantic-memory-agent-kits/receipts/`.
- `shared/scripts/doctor_core.py`: now verifies semantic-memory HTTP health/integrity, semantic-memory MCP tools, context-governor binary/status, context-governor MCP tools, and known local config paths.
- `shared/scripts/setup-host.py`: shared installer backend for MCP-only hosts, with `--write-project [path]`, `--write-user`, and `--dry-run`.
- Host `scripts/setup.sh` files are now thin wrappers around `setup-host.py`.
- `shared/scripts/benchmark-context-governor.py`: writes benchmark receipts for compaction latency, search latency, receipt id, and compact/original token ratio.
- README gained a capability matrix and copy-paste install blocks.
