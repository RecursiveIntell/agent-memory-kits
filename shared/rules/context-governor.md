# context-governor compaction and receipts

Use context-governor when a session is long, a handoff is needed, or context is about to be compacted.

Rules:

1. Prefer exact current conversation context while available. Compacted summaries are background only.
2. Before risky summarization/handoff, preserve active task, acceptance gates, file paths, failing errors, decisions, commands run, and verification receipts.
3. If context-governor MCP tools are available, use:
   - `cg_search` to find prior compaction receipts;
   - `cg_expand` to recover exact fallback text for a receipt item;
   - `cg_diff_receipt` to inspect kept/summarized/omitted/quarantined counts and warnings.
4. If shell is available and a transcript JSON can be exported, compact and store a receipt with:

   ```bash
   /ABSOLUTE/PATH/TO/semantic-memory-agent-kits/shared/scripts/context-governor-compact.py --input transcript.json
   ```

5. If no transcript export is available, create a concise handoff manually with the same policy and include any receipt ids, command outputs, file paths, and unresolved gates.
6. Never treat a compaction receipt as proof that work succeeded. Receipts prove what context was preserved and how to recover exact text.
