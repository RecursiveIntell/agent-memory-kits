---
name: memory-setup-doctor
description: Diagnose and repair semantic-memory Codex setup, including plugin install state, MCP binary resolution, memory directory, hooks.json, config.toml, tool approvals, and smoke tests.
---

# Memory Setup Doctor

Use this skill when the user asks whether semantic memory is installed, working, portable across Codex instances, or needs repair.

## Workflow

1. Run the global setup/config merger when portability or fresh Codex instances matter:
   `python3 <plugin-root>/scripts/install-global-config.py`
2. Run the doctor from the plugin root:
   `python3 <plugin-root>/scripts/doctor.py`
3. Run the read-only audit when memory quality, ROI, or graph health is in question:
   `python3 <plugin-root>/scripts/audit_memory.py`
4. Run the recall evaluation harness when retrieval quality or hook thresholds are in question:
   `python3 <plugin-root>/scripts/eval_recall.py`
5. If the doctor reports missing hooks, run:
   `<plugin-root>/scripts/install-global-hooks.sh`
6. If the MCP binary is missing, run:
   `<plugin-root>/scripts/setup.sh`
7. If plugin cache is stale after source edits, update the cachebuster and reinstall:
   `python3 /home/sikmindz/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py <plugin-root>`
   `codex plugin add semantic-memory@personal`
8. Start a new Codex thread after reinstall so new skills and tool manifests are loaded.

## Expected Baseline

- Source plugin: `/home/sikmindz/plugins/semantic-memory`
- Marketplace: `/home/sikmindz/.agents/plugins/marketplace.json`
- Memory dir: `/home/sikmindz/.local/share/semantic-memory`
- Preferred binary: `/home/sikmindz/Coding/Libraries/semantic-memory-mcp/target/release/semantic-memory-mcp`
- Global hooks: `/home/sikmindz/.codex/hooks.json`

## Repair Rules

Preserve user config and unrelated hooks. Merge missing settings instead of replacing whole files. Treat hook and memory failures as non-blocking unless the user explicitly wants enforcement.
