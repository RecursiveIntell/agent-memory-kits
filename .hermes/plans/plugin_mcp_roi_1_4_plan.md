# Plugin/MCP ROI 1-4 implementation plan

Scope: agent-memory-kits Hermes plugin hooks/scripts plus semantic-memory-mcp HTTP/routing behavior where needed. Do not put admin/release tooling into daily prompt surface; keep it as CLI/script + full/admin profile only.

1. Truth floor / P0 validation
   - Treat doctor_core.py as the canonical smoke gate for installed plugin truth.
   - Validate Hermes plugin manifest hook paths and executability.
   - Validate semantic-memory warm HTTP health and /verify-integrity.
   - Validate MCP tools/list for semantic-memory and context-governor.
   - Validate context-governor receipt store and deep compact smoke.
   - Add/keep tests that catch missing manifest hooks and receipt integrity regressions.

2. Evidence Workbench / release gate
   - evidence-workbench.py should run one or more shell gates, emit compact command receipts, fail closed on any nonzero/timeout, and optionally record a summary fact through warm HTTP.
   - proof-packet.py should mechanically join command receipts, claim JSON, and disposition JSON into a SHA-256-addressed proof packet; promote only when disposition=promote and command receipts did not fail.
   - Add tests for promote, reject, failed command, and command-run packet output.

3. Typed tool/action receipts
   - post_tool_use hook should emit high-signal semantic-memory facts only, not raw tool dumps.
   - Include schema/type/trace_id/tool/summary/session/cwd and digest canonicalization.
   - Skip noisy/self-recursive tools and fail open when HTTP is unavailable.
   - Add tests for terminal/write/read/search receipt shape and skip behavior.

4. Centralized routing/classification
   - Hook should prefer server-side /search-routed metadata when class != A and only fall back to /search or stdio if routed HTTP is unavailable.
   - Keep local classifier as lightweight selection hint only; do not duplicate server retrieval decisions.
   - Record /record-outcome only for routed/non-A queries, based on actually emitted recall context.
   - Add tests that D/C queries use /search-routed, A queries use /search, and outcome feedback is guarded.

Verification gauntlet:
- python3 tests/test_proof_packet.py -v
- python3 tests/test_hermes_tool_receipts.py -v
- python3 tests/test_codex_memory_recall.py -v
- python3 tests/test_evidence_workbench.py -v (new)
- python3 tests/test_doctor_truth_floor.py -v (new if needed)
- python3 shared/scripts/doctor_core.py --host hermes --deep --receipt /tmp/agent-memory-doctor-deep.json
- git diff --stat
