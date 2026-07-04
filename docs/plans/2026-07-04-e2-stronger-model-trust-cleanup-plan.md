# E2 Stronger-Model Trust Cleanup Plan

> For Hermes: implement directly with targeted doc cleanup and full-suite verification.

Goal: finish Sprint E2 by removing stale public claims, hardcoded counts, and misleading capability language from the plugin docs after the expanded 114-test stack.

Architecture: Treat manifests and generated docs as source of truth. Public README files should avoid brittle counts unless they are read directly from the manifest or explicitly say they are generated/approximate. Historical plans and analysis files may keep old examples, but public-facing README and marketplace metadata must not drift.

Tech stack: Python unittest, JSON manifests, markdown README docs, existing generate-tool-surface-docs.py.

## Evidence-backed current state

Repo path: /home/sikmindz/Coding/agent-memory-kits
Date: 2026-07-04
Baseline verification:
- `python -m unittest discover tests/` => Ran 114 tests, OK
- `python shared/scripts/generate-tool-surface-docs.py --out /tmp/agent-memory-kits-tool-surface.json` => claim-ledger 5 tools, context-governor 13 commands; semantic-memory profile servers unavailable in this local run, so README must not hardcode their counts.

Stale public surfaces found:
- `hermes/README.md` says 9 skills / 2 commands / 8 scripts / 3 MCP servers, but `hermes/plugin.json` now declares 9 skills / 1 agent / 5 commands / 5 MCP servers, and the script directory includes the admin/proof/audit wrappers.
- `claude/README.md` still says scripts (8), but current script directory includes proof/evidence/admin/audit wrappers.
- `codex/README.md` says scripts (16), current script directory has extra proof/evidence/admin/audit wrappers.
- Root README repo tree uses fixed script counts in comments that are now stale.
- Generated `__pycache__` files are present under plugin script directories and should not remain in the working tree.

## Task E2.1: Make Hermes README manifest-truthful

Files:
- Modify: `hermes/README.md`

Steps:
1. Replace fixed command/script/MCP counts with manifest-backed statements.
2. Add `/memory-gaps`, `/evidence-workbench`, `/proof-packet` to the commands section.
3. Add admin server and forge-admin to the MCP manifest description.
4. Keep profile tool counts generated-only.

Verification:
- `python -m json.tool hermes/plugin.json`
- `grep -n "2 slash commands\|8 scripts\|3 MCP servers" hermes/README.md` returns no matches.

## Task E2.2: Make Claude/Codex README script counts non-brittle

Files:
- Modify: `claude/README.md`
- Modify: `codex/README.md`

Steps:
1. Replace fixed script counts with “script wrappers include …”.
2. Mention proof/evidence/admin/audit wrappers where present.
3. Avoid exact counts unless mechanically generated.

Verification:
- `grep -n "Scripts (8)\|Scripts (16)" claude/README.md codex/README.md` returns no matches.

## Task E2.3: Clean root README stale tree comments

Files:
- Modify: `README.md`

Steps:
1. Replace “7 .py + run-server.sh” comments with “MCP wrappers, hooks, doctor, ingest, proof/audit helpers”.
2. Keep the architecture and capability claims intact but avoid stale exact counts.

Verification:
- `grep -n "7 .py + run-server.sh" README.md` returns no matches.

## Task E2.4: Remove generated pycache artifacts

Files:
- Remove: `**/__pycache__/` under `agent-memory-kits` working tree

Verification:
- `find . -path '*/__pycache__/*' -print | head` returns no output.

## Task E2.5: Full gauntlet and receipt

Commands:
- `python -m unittest discover tests/`
- `python shared/scripts/release-gate-v2.py --claim "E2 trust cleanup complete" --cmd "python -m unittest discover tests/" --cwd /home/sikmindz/Coding/agent-memory-kits --no-memory --out-dir /tmp/e2-trust-cleanup-proof`

Safe claim after this plan:
- “Public docs no longer hardcode stale command/script/tool counts for the updated plugin stack.”

Not safe to claim:
- “The tool surface is fully counted locally” when semantic-memory profile servers are unavailable.
- “Receipts prove correctness” — receipts prove command execution, boundaries, and evidence state.
