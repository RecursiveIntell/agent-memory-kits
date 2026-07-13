---
description: One-time setup for semantic memory — install the binary, allow its tools without prompts, and verify the server connects.
---

Perform one-time setup so the semantic-memory plugin is fully operational. Do these steps and report results concisely:

1. **Binary check / install.** Run `command -v semantic-memory-mcp || ls ~/.cargo/bin/semantic-memory-mcp ~/.local/bin/semantic-memory-mcp 2>/dev/null`. If it is not found, install it: `cargo install semantic-memory-mcp` (requires Rust/cargo — if cargo is missing, tell the user to install Rust from https://rustup.rs first and stop).

2. **Permission allowlist.** So the `sm_*` tools never prompt, ensure `~/.claude/settings.json` has `"mcp__semantic-memory"` in `permissions.allow`. Read the file first and merge (do not clobber existing settings). If it is absent, add it.

3. **Memory store.** Confirm the parent directory exists for the database file (default `$HOME/.hermes/semantic-memory.db`, or `$SEMANTIC_MEMORY_DIR`). `SEMANTIC_MEMORY_DIR` is a **file path**, not a directory; the runtime creates only its parent directory (`$HOME/.hermes`) on first use. Context-governor receipts use the separate directory `$HOME/.hermes/context-governor` (or `$CONTEXT_GOVERNOR_STORE`).

4. **Verify.** Confirm the MCP server is connected (`claude mcp list` should show `semantic-memory` ✓, or the plugin's bundled server). If the model (`nomic-embed-text-v1.5`, ~550 MB) hasn't been downloaded yet, note that the first `sm_add_fact`/`sm_search` will fetch it once and cache it.

5. Report what was already in place vs. what you changed, and confirm the hooks (auto-recall on prompt, session primer, pre-compaction nudge) are active via this plugin.
