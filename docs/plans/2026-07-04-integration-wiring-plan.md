# Integration Wiring Plan — connect tested modules to live plugin pipeline

Date: 2026-07-04
Goal: Wire the 5 tested-but-unintegrated modules into the live plugin stack.

## Current state

Tested but NOT wired into live pipeline:
1. recall_admission.py — module exists, tests pass, but sm-recall.py does not call it
2. forge-admin-mcp.py — script exists, tests pass, but plugin.json does not declare it
3. admin-preflight.py — script exists, tests pass, but run-server-admin.sh does not call it
4. generate-tool-surface-docs.py — script exists, but doctor does not check for drift
5. trace_ids.py — module exists, but no receipt-emitting script uses it

## Integration tasks

### Task 1: Wire recall-admission into sm-recall.py
File: hermes/hooks/sm-recall.py
File: codex/plugins/semantic-memory/hooks/memory-recall.py

After prepare_hits() returns the filtered hit list and before the score-based
filtering (line ~185 in sm-recall.py), insert recall-admission evaluation:
- Import recall_admission (via sys.path manipulation since it's in shared/scripts)
- Create a RecallAdmissionLedger with path $SEMANTIC_MEMORY_DIR/recall-admission.jsonl
- For each hit, call ledger.evaluate() with query terms, result content terms, namespace, score
- Filter out hits where record.admitted is False
- Write all admission records to the ledger
- Add a debug line showing how many were filtered

### Task 2: Add forge-admin MCP server to plugin.json
File: hermes/plugin.json

Add a new entry under mcp_servers:
  "forge-admin": {
    "command": "python3",
    "args": ["scripts/forge-admin-mcp.py"]
  }

Create: hermes/scripts/forge-admin-mcp.py (thin wrapper to shared/scripts)

### Task 3: Wire admin-preflight into run-server-admin.sh
File: shared/scripts/run-server-admin.sh

Before the semantic-memory-mcp admin server starts, call admin-preflight preflight
with operation=reembed_missing or similar. After the server stops, call postflight.
This is a documentation/intent layer, not a hard gate — the admin server itself
handles the actual operations.

### Task 4: Add tool-surface drift check to doctor
File: shared/scripts/doctor_core.py

In the deep path, after claim_ledger_check(), add a check that:
- Runs generate-tool-surface-docs.py --out /tmp/doctor-tool-surface.json
- Reads the generated artifact
- Warns if any profile tool_count is None (unavailable)
- Reports the counts in the doctor output

### Task 5: Add trace_ids to receipt-emitting scripts
Files: release-gate-v2.py (already has it), evidence-workbench.py,
context-governor-audit.py, verify-patch.py, benchmark-recall.py, admin-preflight.py

Add TraceCtx.create() to each script's output JSON if not already present.
release-gate-v2.py already has trace_id — the others need it added.

## Verification

After all tasks:
1. Run all tests: python -m unittest discover tests/
2. Run doctor deep: python shared/scripts/doctor_core.py --host hermes --deep
3. Run release gate: python shared/scripts/release-gate-v2.py --claim "integration wired" --cmd "python -m unittest discover tests/" --cwd . --no-memory --out-dir /tmp/integration-proof