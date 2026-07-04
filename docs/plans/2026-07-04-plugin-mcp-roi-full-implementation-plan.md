# Plugin/MCP ROI Full Implementation Plan (2026-07-04)

> **For Hermes:** Implement this plan in sprint order (A, B, C, D). Use TDD for all behavior changes. Every shipped item needs a receipt from targeted tests/smokes. Do not commit unless explicitly asked.

**Goal:** Turn the agent-memory-kits plugin stack from a memory add-on into an admission-controlled, receipt-backed, side-effect-aware, evidence-producing operator-grade memory runtime. Implement all 10 ROI items from the 2026-07-04 re-examination, with special attention to Forge/CEA as a separate patch-verification surface.

**Architecture:** Keep `semantic-memory-mcp`, `context-governor`, and `claim-ledger` as companion MCP servers. Implement product glue in `agent-memory-kits/shared/scripts` and thin host wrappers. Keep daily MCP profiles lean; proof/release/admin/forge workflows live in scripts or admin/full profile only. Forge/CEA gets its own sprint (D) and its own admin command path, never daily recall.

**Tech Stack:** Python hook scripts, Bash wrappers, JSON plugin manifests, Rust context-governor CLI/library, semantic-memory-mcp HTTP/MCP, claim-ledger companion, stack-ids/receipt-bench/verification crates, forge-engine/cea-core/typed-patch/check-runner/sandbox-workspace for Sprint D.

---

## Source inventory checked

Reports read end-to-end:
- `/home/sikmindz/Coding/Libraries/_analysis/unreleased_crate_roi_2026-07-03/ROI_REPORT.md` (1253 lines, 39 unreleased crates audited)
- `/home/sikmindz/Coding/Libraries/_analysis/unreleased_crate_roi_2026-07-03/PLUGIN_MCP_AND_ESP32_HIGHEST_ROI.md` (472 lines)
- `/home/sikmindz/Coding/Libraries/_analysis/unreleased_crate_roi_2026-07-03/CURRENT_PROJECT_HIGHEST_ROI_USAGE.md` (518 lines)
- `/home/sikmindz/Coding/agent-memory-kits/_analysis/plugin_mcp_next_highest_roi_2026-07-04.md` (369 lines, the 10-item re-examination)
- `/home/sikmindz/Coding/agent-memory-kits/docs/plans/2026-07-03-plugin-stack-roi-implementation-plan.md` (205 lines, prior P0-P2 plan)
- `/home/sikmindz/Coding/agent-memory-kits/.hermes/plans/2026-07-03_000000-plugin-mcp-roi-1-4.md` (147 lines, prior 1-4 plan)
- `/home/sikmindz/Coding/agent-memory-kits/.hermes/plans/plugin_mcp_roi_1_4_plan.md` (37 lines, prior 1-4 outline)

Codebase state verified:
- `agent-memory-kits/hermes/plugin.json` — declares 4 hooks, 4 MCP servers, 9 skills, 1 agent, 4 commands
- `agent-memory-kits/shared/scripts/` — 19 scripts including doctor_core.py, evidence-workbench.py, proof-packet.py, claim-ledger-mcp.py, context-governor-mcp.py
- `agent-memory-kits/tests/` — 6 test files covering doctor truth floor, proof packet, evidence workbench, tool receipts, codex recall, hermes routing
- `agent-memory-kits/hermes/hooks/` — 5 hook files (common.py, sm-recall.py, sm-auto-edge.py+sh, sm-conversation-capture.py, sm-primer.py)
- `Libraries/context-governor/src/high_roi.rs` — 6 public audit functions already implemented
- `Libraries/living-memory/living-memory/src/` — forge-engine with cea/, exec/, store/, lab/ modules, full CEA pipeline
- `Libraries/Primitives/cea-core/src/` — attribution, calibration, graph, predict, scope, types modules
- `Libraries/Primitives/typed-patch/src/` — structured patch validation/apply with forge-policy integration
- `forge-workbench/` — existing Tauri app already depending on forge-engine, typed-patch, semantic-memory, stack-ids, ai-batch-queue, tauri-queue
- `Libraries/semantic-memory-mcp/Cargo.toml` — v0.4.0, features: search/full/claim-integration/llm-parser/orchestration/hnsw

Prior P0 (items 1-4 from the 2026-07-03 plan) status:
- P0 hook manifest validation: implemented, doctor_core.py exists with truth-floor checks
- Evidence Workbench v1: implemented, evidence-workbench.py + proof-packet.py exist with tests
- Typed tool receipts: implemented, sm-auto-edge.py emits digest-only receipts with tests
- Server-side routing: implemented, hooks prefer /search-routed for non-A queries with tests

This plan implements the 10 next-highest-ROI items from the 2026-07-04 re-examination.

---

## Forge/CEA analysis: standalone vs integrated

### What Forge/CEA is

A local-first agent patch evaluation system:
- typed-patch: structured edit objects (file edits, anchors, line ranges, validation)
- sandbox-workspace: safe staging for patch application
- check-runner: normalized command/check execution with timing/effect capture
- cea-core: converts patches + check results into weighted cause/effect attribution triples, learns graph weights, predicts future edit risk
- cea-store/cea-sqlite: persistence for CEA graphs
- forge-engine: the operational engine that ties it all together (compile mindstate, apply patches, run checks, score outcomes, persist evidence, update CEA)
- forge-pilot: OODA orchestrator over the full loop
- effect-signature: stable effect payloads for normalized check output comparison
- stabilizer-core: bounded fix attempt phases (innovate/stabilize/clamp)
- mindstate-core: serializable agent intent payloads
- forge-policy: filesystem/env/patch-cap guardrails

### ROI comparison

**Integrated into plugin stack (admin path):**
- ROI: 8/10 for current projects
- Pro: directly usable by Hermes/Codex/Claude agents via admin command
- Pro: shares claim-ledger/semantic-memory/verification stack already wired
- Pro: forge-workbench already exists as GUI
- Con: adds complexity to plugin distribution
- Con: 6/10 for broad public plugin until polished

**Standalone (separate repo/tool):**
- ROI: 9/10 if positioned as "Forge: causal edit attribution and receipt-backed patch verification"
- Pro: clear public story: "Know which agent edit caused which check result"
- Pro: coherent 12-crate family that tells one story
- Pro: can be published as recursiveintell/forge with its own README/diagrams
- Pro: forge-workbench is the GUI companion, not buried in a plugin kit
- Pro: standalone Forge can feed into multiple consumers (plugin stack, forge-workbench, Recall-Coding, future CI)
- Con: needs README/diagram work before public
- Con: needs dry-run packaging fixes before crates.io

### Recommendation: DO BOTH, sequentially

1. Build the plugin admin path first (Sprint D below) — proves the integration works
2. Extract to standalone repo after the admin path is receipt-verified
3. Publish the Forge crate family to crates.io after dry-run fixes + README upgrades
4. Wire forge-workbench as the GUI consumer of the standalone crates

The standalone path has higher long-term ROI but the integrated path is the fastest proof. Build the integration first, extract second.

---

## Sprint A: fastest high-ROI foundation

### Task A1: Add context-governor high_roi audit wrapper

**Objective:** Expose the 6 audit functions from `context-governor/src/high_roi.rs` as a CLI/script wrapper and admin MCP tools.

**Files:**
- Create: `shared/scripts/context-governor-audit.py`
- Create: `tests/test_context_governor_audit.py`
- Modify: `shared/scripts/doctor_core.py` (add audit gate)
- Modify: `hermes/scripts/context-governor-audit.py` (thin wrapper)
- Modify: `codex/plugins/semantic-memory/scripts/context-governor-audit.py` (thin wrapper)
- Modify: `claude/plugins/semantic-memory/scripts/context-governor-audit.py` (thin wrapper)

**Context-governor API surface (verified from source):**
- `evaluate_governed_memory(harness_id, cases) -> GovernedMemoryHarnessReceiptV1`
- `audit_mcp_tool_surface(tools: &[ToolManifestEntry]) -> McpToolSurfaceAuditV1`
- `audit_compression_boundary(...)` -> `CompressionBoundaryAuditV1`
- `evaluate_leakage_free_rag(input: RagEvalInput) -> RagLeakageReceiptV1`
- `screen_knowledge_conflicts(claims: &[EvidenceClaim]) -> ConflictScreenReportV1`
- `select_retrieval_route(query: &str) -> RetrievalRouteDecisionV1`

**Step 1: Write failing test**

```python
# tests/test_context_governor_audit.py
import unittest
import json
import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'context-governor-audit.py')

class TestContextGovernorAudit(unittest.TestCase):
    def test_tool_surface_audit_runs(self):
        """cg_audit_tool_surface should produce a valid audit receipt."""
        result = subprocess.run(
            [sys.executable, SCRIPT, 'audit-tool-surface',
             '--tools-json', json.dumps([
                 {"name": "sm_search", "description": "Search the knowledge base"},
                 {"name": "sm_add_fact", "description": "Add a fact to the knowledge base"}
             ])],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['schema'], 'McpToolSurfaceAuditV1')
        self.assertIn('findings', receipt)
        self.assertIn('risk_level', receipt)

    def test_select_retrieval_route_runs(self):
        """cg_select_retrieval_route should return a route decision."""
        result = subprocess.run(
            [sys.executable, SCRIPT, 'select-route', '--query', 'what are the latest ROI items'],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        decision = json.loads(result.stdout)
        self.assertEqual(decision['schema'], 'RetrievalRouteDecisionV1')
        self.assertIn('route', decision)

    def test_screen_conflicts_runs(self):
        """cg_screen_conflicts should detect conflicting claims."""
        result = subprocess.run(
            [sys.executable, SCRIPT, 'screen-conflicts',
             '--claims-json', json.dumps([
                 {"id": "c1", "text": "The system supports 48 tools"},
                 {"id": "c2", "text": "The system does not support 48 tools"}
             ])],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        report = json.loads(result.stdout)
        self.assertEqual(report['schema'], 'ConflictScreenReportV1')
        self.assertIn('findings', report)

    def test_fail_open_on_missing_binary(self):
        """Script should fail open with exit 0 and clear message if context-governor binary absent."""
        # This test validates fail-open behavior when the Rust binary is not installed
        result = subprocess.run(
            [sys.executable, SCRIPT, 'audit-tool-surface', '--tools-json', '[]',
             '--binary-path', '/nonexistent/context-governor'],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('context-governor', result.stderr.lower() + result.stdout.lower())

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify failure**

```bash
cd /home/sikmindz/Coding/agent-memory-kits
python -m unittest tests/test_context_governor_audit.py -v
```
Expected: FAIL — script does not exist yet.

**Step 3: Implement the audit wrapper script**

```python
#!/usr/bin/env python3
"""context-governor-audit.py — expose high_roi.rs audit functions as CLI.

Subcommands:
  audit-tool-surface   — audit MCP tool descriptions for split-instruction/selection risks
  audit-compression     — audit compression boundary for source-fragment relinking
  eval-governed-memory  — evaluate memory governance cases
  eval-rag-leakage      — evaluate retrieval leakage-free RAG
  screen-conflicts      — screen knowledge claims for conflicts
  select-route          — select retrieval route for a query

All subcommands fail open (exit 0 with stderr message) if the context-governor
binary is absent or errors.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

DEFAULT_BINARY = shutil.which("context-governor") or os.path.join(
    os.path.expanduser("~"), ".cargo", "bin", "context-governor"
)

def run_cg(binary_path, args, stdin_data=None):
    """Run context-governor binary, fail open on missing/error."""
    if not os.path.isfile(binary_path) or not os.access(binary_path, os.X_OK):
        print(f"context-governor binary not found at {binary_path}", file=sys.stderr)
        sys.exit(0)
    try:
        result = subprocess.run(
            [binary_path] + args,
            input=stdin_data,
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"context-governor error: {result.stderr}", file=sys.stderr)
            sys.exit(0)
        return result.stdout
    except subprocess.TimeoutExpired:
        print("context-governor timed out", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"context-governor exception: {e}", file=sys.stderr)
        sys.exit(0)

def cmd_audit_tool_surface(args):
    tools_json = args.tools_json or json.dumps([])
    output = run_cg(args.binary_path, [
        "audit-tool-surface", "--tools-json", tools_json
    ])
    print(output)

def cmd_audit_compression(args):
    output = run_cg(args.binary_path, [
        "audit-compression-boundary",
        "--source-text", args.source_text or "",
        "--compressed-text", args.compressed_text or ""
    ])
    print(output)

def cmd_eval_governed_memory(args):
    cases_json = args.cases_json or json.dumps([])
    output = run_cg(args.binary_path, [
        "eval-governed-memory",
        "--harness-id", args.harness_id or "default",
        "--cases-json", cases_json
    ])
    print(output)

def cmd_eval_rag_leakage(args):
    output = run_cg(args.binary_path, [
        "eval-rag-leakage",
        "--query", args.query or "",
        "--retrieved", args.retrieved or "",
        "--model-answer", args.model_answer or ""
    ])
    print(output)

def cmd_screen_conflicts(args):
    claims_json = args.claims_json or json.dumps([])
    output = run_cg(args.binary_path, [
        "screen-conflicts", "--claims-json", claims_json
    ])
    print(output)

def cmd_select_route(args):
    output = run_cg(args.binary_path, [
        "select-route", "--query", args.query or ""
    ])
    print(output)

def main():
    parser = argparse.ArgumentParser(description="context-governor high_roi audit wrapper")
    parser.add_argument("--binary-path", default=DEFAULT_BINARY, help="path to context-governor binary")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("audit-tool-surface")
    p.add_argument("--tools-json", help="JSON array of {name, description}")
    p.set_defaults(func=cmd_audit_tool_surface)

    p = sub.add_parser("audit-compression")
    p.add_argument("--source-text")
    p.add_argument("--compressed-text")
    p.set_defaults(func=cmd_audit_compression)

    p = sub.add_parser("eval-governed-memory")
    p.add_argument("--harness-id")
    p.add_argument("--cases-json", help="JSON array of GovernanceCase")
    p.set_defaults(func=cmd_eval_governed_memory)

    p = sub.add_parser("eval-rag-leakage")
    p.add_argument("--query")
    p.add_argument("--retrieved")
    p.add_argument("--model-answer", dest="model_answer")
    p.set_defaults(func=cmd_eval_rag_leakage)

    p = sub.add_parser("screen-conflicts")
    p.add_argument("--claims-json", help="JSON array of {id, text}")
    p.set_defaults(func=cmd_screen_conflicts)

    p = sub.add_parser("select-route")
    p.add_argument("--query")
    p.set_defaults(func=cmd_select_route)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
```

**Step 4: Create thin host wrappers**

Each host wrapper (hermes/scripts/, codex/plugins/.../scripts/, claude/plugins/.../scripts/) is a 3-line shim:
```python
#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared', 'scripts'))
from context_governor_audit import main
main()
```

**Step 5: Add doctor audit gate**

In `doctor_core.py`, add a check that runs `context-governor-audit.py audit-tool-surface` against the semantic-memory, context-governor, and claim-ledger MCP tool manifests. Store the audit receipt in the doctor output.

**Step 6: Run tests to verify pass**

```bash
python -m unittest tests/test_context_governor_audit.py -v
```
Expected: PASS (or fail-open skip if context-governor binary not installed)

**Step 7: Commit**

```bash
git add shared/scripts/context-governor-audit.py tests/test_context_governor_audit.py hermes/scripts/context-governor-audit.py codex/plugins/semantic-memory/scripts/context-governor-audit.py claude/plugins/semantic-memory/scripts/context-governor-audit.py shared/scripts/doctor_core.py
git commit -m "feat: add context-governor high_roi audit wrapper with 6 audit functions"
```

---

### Task A2: Generate tool-surface docs and add doctor check

**Objective:** Mechanically generate MCP tool counts/descriptions for lean/standard/full/admin profiles so README/docs never drift from live tool surface.

**Files:**
- Create: `shared/scripts/generate-tool-surface-docs.py`
- Create: `tests/test_tool_surface_docs.py`
- Modify: `shared/scripts/doctor_core.py` (add tool-surface drift check)
- Modify: `README.md` (reference generated docs, remove hand-maintained counts)

**Step 1: Write failing test**

```python
# tests/test_tool_surface_docs.py
import unittest
import json
import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'generate-tool-surface-docs.py')

class TestToolSurfaceDocs(unittest.TestCase):
    def test_generates_json_artifact(self):
        """generate-tool-surface-docs.py should produce a JSON artifact with profile counts."""
        result = subprocess.run(
            [sys.executable, SCRIPT, '--out', '/tmp/test-tool-surface.json',
             '--format', 'json'],
            capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        with open('/tmp/test-tool-surface.json') as f:
            doc = json.load(f)
        self.assertIn('profiles', doc)
        # At least lean profile should be present
        self.assertIn('lean', doc['profiles'] or {})
        # Each profile should have a tool_count
        for profile_name, profile_data in doc['profiles'].items():
            self.assertIn('tool_count', profile_data)

    def test_doctor_checks_drift(self):
        """Doctor should warn if README advertised count does not match generated count."""
        # This is a smoke test that doctor includes a tool-surface drift check
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'doctor_core.py'),
             '--host', 'hermes', '--receipt', '/tmp/test-doctor-ts.json'],
            capture_output=True, text=True, timeout=60
        )
        # Doctor should pass or warn, not crash
        self.assertIn(result.returncode, [0, 1])

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify failure**

**Step 3: Implement generate-tool-surface-docs.py**

The script should:
1. Call `semantic-memory-mcp --tool-profile lean --list-tools` (or MCP tools/list) for each profile
2. Call `context-governor` tool list if available
3. Call `claim-ledger` tool list if available
4. Write a JSON artifact with per-profile tool counts, tool names, descriptions
5. Optionally write a markdown table

**Step 4: Add doctor drift check**

Doctor reads the generated JSON artifact and compares advertised counts in README/plugin.json against actual. Warn on mismatch.

**Step 5: Run tests, commit**

---

### Task A3: Add recall-admission JSONL receipts with hubness gating

**Objective:** Record why each recall candidate was admitted or rejected, with global/namespace hit frequency tracking to block hub candidates.

**Files:**
- Create: `shared/scripts/recall-admission.py`
- Modify: `hermes/hooks/sm-recall.py` (emit admission receipts)
- Modify: `codex/plugins/semantic-memory/hooks/memory-recall.py` (emit admission receipts)
- Create: `tests/test_recall_admission.py`

**Step 1: Write failing test**

```python
# tests/test_recall_admission.py
import unittest
import json
import os
import tempfile
from shared.scripts.recall_admission import RecallAdmissionLedger, AdmissionRecord

class TestRecallAdmission(unittest.TestCase):
    def test_admit_candidate(self):
        """Admitted candidate gets a receipt with admitted=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = RecallAdmissionLedger(os.path.join(tmpdir, 'admission.jsonl'))
            record = ledger.evaluate(
                query="what are the ROI items",
                result_id="fact:abc123",
                namespace="general",
                score=0.85,
                cosine=0.92,
                query_terms=["roi", "items"],
                result_terms=["roi", "audit", "items"],
                namespace_match=True
            )
            self.assertTrue(record.admitted)
            self.assertIsNone(record.reject_reason)
            ledger.write(record)
            # Verify file exists and has one line
            with open(os.path.join(tmpdir, 'admission.jsonl')) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertTrue(entry['admitted'])

    def test_reject_hub(self):
        """High-frequency hub candidate is rejected unless strong overlap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = RecallAdmissionLedger(os.path.join(tmpdir, 'admission.jsonl'))
            # Simulate a fact that appears in many queries (hub)
            for i in range(20):
                ledger.evaluate(
                    query=f"query {i}",
                    result_id="fact:hub",
                    namespace="general",
                    score=0.5,
                    cosine=0.6,
                    query_terms=[f"term{i}"],
                    result_terms=["generic", "project", "profile"],
                    namespace_match=False
                )
            # The 21st query should reject the hub
            record = ledger.evaluate(
                query="specific technical question",
                result_id="fact:hub",
                namespace="general",
                score=0.55,
                cosine=0.62,
                query_terms=["specific", "technical"],
                result_terms=["generic", "project", "profile"],
                namespace_match=False
            )
            self.assertFalse(record.admitted)
            self.assertIn('hub', record.reject_reason.lower())

    def test_admit_hub_with_strong_overlap(self):
        """Hub candidate is admitted if exact term overlap is strong."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = RecallAdmissionLedger(os.path.join(tmpdir, 'admission.jsonl'))
            for i in range(20):
                ledger.evaluate(
                    query=f"query {i}",
                    result_id="fact:hub",
                    namespace="research",
                    score=0.5,
                    cosine=0.6,
                    query_terms=[f"term{i}"],
                    result_terms=["forge", "cea", "patch"],
                    namespace_match=False
                )
            # Strong overlap query should still admit
            record = ledger.evaluate(
                query="forge cea patch verification",
                result_id="fact:hub",
                namespace="research",
                score=0.7,
                cosine=0.75,
                query_terms=["forge", "cea", "patch", "verification"],
                result_terms=["forge", "cea", "patch"],
                namespace_match=True
            )
            self.assertTrue(record.admitted)

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify failure**

**Step 3: Implement recall-admission.py**

Core logic:
- `RecallAdmissionLedger` class with JSONL append store
- `evaluate()` method that:
  1. Computes global hit frequency for result_id (how many queries returned it)
  2. Computes namespace hit frequency
  3. Computes term overlap ratio (query terms ∩ result terms / query terms)
  4. Applies gating rules:
     - reject if global_hit_frequency > 15 AND term_overlap < 0.3 AND not namespace_match
     - demote if score < 0.4 AND not namespace_match
     - boost if namespace_match AND term_overlap > 0.5
  5. Returns AdmissionRecord with admitted bool and reject_reason
- `write()` method appends to JSONL
- `stats()` method returns hub statistics

**Step 4: Wire into hooks**

In sm-recall.py and memory-recall.py, after getting search results:
1. Import recall_admission
2. For each result, call `ledger.evaluate()`
3. Filter out non-admitted results before injection
4. Write admission receipts to `$SEMANTIC_MEMORY_DIR/recall-admission.jsonl`

**Step 5: Run tests, commit**

---

### Task A4: Add receipt-bench recall benchmark command

**Objective:** Replace ad-hoc recall eval scripts with receipt-bench-backed reports.

**Files:**
- Create: `shared/scripts/benchmark-recall-receipted.sh`
- Create: `shared/scripts/benchmark-recall.py`
- Create: `tests/test_benchmark_recall.py`
- Use existing fixtures: `shared/fixtures/code-search.jsonl`, `conversation-recall.jsonl`, `contradiction-check.jsonl`

**Step 1: Write failing test**

```python
# tests/test_benchmark_recall.py
import unittest
import json
import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'benchmark-recall.py')

class TestBenchmarkRecall(unittest.TestCase):
    def test_runs_against_fixtures(self):
        """benchmark-recall.py should run against existing fixtures and emit a receipt."""
        fixtures_dir = os.path.join(os.path.dirname(__file__), '..', 'shared', 'fixtures')
        result = subprocess.run(
            [sys.executable, SCRIPT,
             '--fixtures-dir', fixtures_dir,
             '--out', '/tmp/test-benchmark-receipt.json'],
            capture_output=True, text=True, timeout=120
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        with open('/tmp/test-benchmark-receipt.json') as f:
            receipt = json.load(f)
        self.assertIn('schema', receipt)
        self.assertIn('recall_at_k', receipt)
        self.assertIn('fixtures_used', receipt)

    def test_fails_open_on_missing_fixtures(self):
        """Script should fail open with clear message if fixtures dir missing."""
        result = subprocess.run(
            [sys.executable, SCRIPT, '--fixtures-dir', '/nonexistent', '--out', '/tmp/test-bm-empty.json'],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('fixtures', result.stderr.lower())

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify failure**

**Step 3: Implement benchmark-recall.py**

Core logic:
- Load JSONL fixtures (query, expected_result_ids, namespace_filter)
- For each fixture, call semantic-memory HTTP /search with the query
- Compute recall@k, nDCG@k, reciprocal rank
- Emit receipt-bench-compatible JSON receipt with:
  - schema: `SMBenchmarkReport`
  - commit_hash (git rev-parse HEAD)
  - machine_fingerprint (hostname + platform)
  - timestamp
  - fixtures_used count
  - recall_at_k, ndcg_at_k, mrr
  - per-fixture breakdown

**Step 4: Create benchmark-recall-receipted.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/benchmark-recall.py" \
  --fixtures-dir "$SCRIPT_DIR/../fixtures" \
  --out "$SCRIPT_DIR/../_receipts/recall-benchmark-$(date +%Y%m%dT%H%M%SZ).json"
```

**Step 5: Run tests, commit**

---

## Sprint B: proof pipeline

### Task B1: Upgrade Evidence Workbench to v2 with claim-ledger + verification crates

**Objective:** Turn evidence-workbench from a command-runner into a real claim-ledger + verification-control proof packet pipeline.

**Files:**
- Create: `shared/scripts/release-gate-v2.py`
- Modify: `shared/scripts/evidence-workbench.py` (keep as fallback, add --v2 flag)
- Modify: `shared/scripts/proof-packet.py` (accept v2 input)
- Create: `tests/test_release_gate_v2.py`

**Step 1: Write failing test**

```python
# tests/test_release_gate_v2.py
import unittest
import json
import subprocess
import sys
import os
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'release-gate-v2.py')

class TestReleaseGateV2(unittest.TestCase):
    def test_produces_proof_packet_with_disposition(self):
        """release-gate-v2 should emit a proof packet with adjudication disposition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, SCRIPT,
                 '--claim', 'Focused tests pass',
                 '--cmd', 'python -m unittest tests/test_proof_packet.py -v',
                 '--cwd', os.path.join(os.path.dirname(__file__), '..'),
                 '--out-dir', tmpdir,
                 '--no-memory'],
                capture_output=True, text=True, timeout=120
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            # Check proof packet exists
            packets = [f for f in os.listdir(tmpdir) if f.endswith('.json')]
            self.assertTrue(len(packets) > 0, "No proof packet emitted")
            with open(os.path.join(tmpdir, packets[0])) as f:
                packet = json.load(f)
            self.assertIn('disposition', packet)
            self.assertIn(packet['disposition'], ['promote', 'reject', 'quarantine', 'defer'])
            self.assertIn('command_receipts', packet)
            self.assertIn('claim', packet)

    def test_rejects_on_failing_command(self):
        """release-gate-v2 should reject when a command fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, SCRIPT,
                 '--claim', 'This should fail',
                 '--cmd', 'false',
                 '--cwd', '/tmp',
                 '--out-dir', tmpdir,
                 '--no-memory'],
                capture_output=True, text=True, timeout=30
            )
            self.assertNotEqual(result.returncode, 0)
            packets = [f for f in os.listdir(tmpdir) if f.endswith('.json')]
            if packets:
                with open(os.path.join(tmpdir, packets[0])) as f:
                    packet = json.load(f)
                self.assertEqual(packet['disposition'], 'reject')

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify failure**

**Step 3: Implement release-gate-v2.py**

Pipeline:
1. Parse claim, commands, cwd, out-dir
2. Run each command, capture exit_code, stdout, stderr, timing
3. Build command receipts (schema: `release-gate-command-receipt-v1`)
4. Build claim JSON
5. Evaluate: if any command exit_code != 0, disposition = reject
6. If all pass, disposition = promote
7. Build proof packet JSON with:
   - schema: `ReleaseGateProofPacketV1`
   - claim
   - command_receipts
   - disposition
   - packet_sha256
   - timestamp
   - git_commit (if available)
8. Optionally call claim-ledger MCP to store claim + evidence
9. Optionally call semantic-memory to store durable fact with evidence refs
10. Write packet to out-dir

**Step 4: Run tests, commit**

---

### Task B2: Make claim-ledger verification part of doctor deep

**Objective:** `cl_ledger_verify` runs as part of `doctor_core.py --deep`.

**Files:**
- Modify: `shared/scripts/doctor_core.py`
- Create: `tests/test_doctor_claim_ledger.py`

**Step 1: Write failing test**

```python
# tests/test_doctor_claim_ledger.py
import unittest
import subprocess
import sys
import os

DOCTOR = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'doctor_core.py')

class TestDoctorClaimLedger(unittest.TestCase):
    def test_deep_includes_claim_ledger_check(self):
        """Doctor --deep should include a claim-ledger verification check."""
        result = subprocess.run(
            [sys.executable, DOCTOR, '--host', 'hermes', '--deep',
             '--receipt', '/tmp/test-doctor-cl.json'],
            capture_output=True, text=True, timeout=120
        )
        # Doctor should pass or warn (exit 0 or 1), not crash (exit 2)
        self.assertIn(result.returncode, [0, 1])
        # Check receipt for claim_ledger check
        import json
        if os.path.exists('/tmp/test-doctor-cl.json'):
            with open('/tmp/test-doctor-cl.json') as f:
                receipt = json.load(f)
            checks = receipt.get('checks', [])
            cl_checks = [c for c in checks if 'claim' in c.get('name', '').lower() and 'ledger' in c.get('name', '').lower()]
            self.assertTrue(len(cl_checks) > 0, "No claim-ledger check in doctor deep")

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Implement, run tests, commit**

---

### Task B3: Add stack-ids trace IDs to all generated receipts

**Objective:** Every plugin-generated receipt gets a stable stack-ids-compatible trace ID.

**Files:**
- Create: `shared/scripts/trace_ids.py` (shared helper)
- Modify: `shared/scripts/evidence-workbench.py`
- Modify: `shared/scripts/proof-packet.py`
- Modify: `shared/scripts/release-gate-v2.py`
- Modify: `hermes/hooks/sm-auto-edge.py`
- Modify: `shared/scripts/context-governor-audit.py`
- Modify: `shared/scripts/benchmark-recall.py`
- Create: `tests/test_trace_ids.py`

**Step 1: Write failing test**

```python
# tests/test_trace_ids.py
import unittest
from shared.scripts.trace_ids import generate_trace_id, generate_content_digest, TraceCtx

class TestTraceIds(unittest.TestCase):
    def test_trace_id_format(self):
        """Trace ID should have trace: prefix and be unique."""
        tid1 = generate_trace_id(scope="release-gate")
        tid2 = generate_trace_id(scope="release-gate")
        self.assertTrue(tid1.startswith("trace:release-gate:"))
        self.assertNotEqual(tid1, tid2)

    def test_content_digest_stable(self):
        """Same content should produce same digest."""
        d1 = generate_content_digest("hello world")
        d2 = generate_content_digest("hello world")
        d3 = generate_content_digest("hello world!")
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, d3)
        self.assertTrue(d1.startswith("sha256:"))

    def test_trace_ctx_serializable(self):
        """TraceCtx should be JSON serializable."""
        ctx = TraceCtx(scope="audit", trace_id="trace:audit:abc")
        d = ctx.to_dict()
        self.assertIn('scope', d)
        self.assertIn('trace_id', d)
        ctx2 = TraceCtx.from_dict(d)
        self.assertEqual(ctx2.trace_id, ctx.trace_id)

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Implement trace_ids.py**

Core:
- `generate_trace_id(scope)` -> `f"trace:{scope}:{uuid4.hex[:16]}"`
- `generate_content_digest(content)` -> `f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"`
- `TraceCtx` dataclass with scope, trace_id, timestamp, parent_trace_id (optional)
- JSON serializable

**Step 3: Wire into all receipt-emitting scripts**

Each script imports `trace_ids` and adds `trace_ctx` to its output JSON.

**Step 4: Run tests, commit**

---

## Sprint C: side-effect safety

### Task C1: Add admin action preflight using effect-runtime + verification-policy

**Objective:** Admin operations (hard delete, import, re-embed all, reconcile, vacuum, export bundle, release-gate promotion) must emit EffectIntent + preflight report before running, and EffectExecutionReceipt after.

**Files:**
- Create: `shared/scripts/admin-preflight.py`
- Modify: `shared/scripts/run-server-admin.sh` (call preflight before admin MCP commands)
- Create: `tests/test_admin_preflight.py`

**Step 1: Write failing test**

```python
# tests/test_admin_preflight.py
import unittest
import json
import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'admin-preflight.py')

class TestAdminPreflight(unittest.TestCase):
    def test_emits_effect_intent_for_delete(self):
        """admin-preflight should emit EffectIntentV1 for delete_namespace."""
        result = subprocess.run(
            [sys.executable, SCRIPT, 'preflight',
             '--operation', 'delete_namespace',
             '--target', 'test-namespace',
             '--operator', 'test'],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        intent = json.loads(result.stdout)
        self.assertEqual(intent['schema'], 'EffectIntentV1')
        self.assertEqual(intent['operation'], 'delete_namespace')
        self.assertIn('target', intent)
        self.assertIn('risk_level', intent)

    def test_blocks_destructive_without_confirmation(self):
        """admin-preflight should block destructive ops without --confirm."""
        result = subprocess.run(
            [sys.executable, SCRIPT, 'preflight',
             '--operation', 'delete_namespace',
             '--target', 'production-namespace',
             '--operator', 'test'],
            capture_output=True, text=True, timeout=30
        )
        # Should emit a block receipt, not proceed
        output = json.loads(result.stdout)
        self.assertIn('blocked', output)
        self.assertTrue(output['blocked'] or output.get('risk_level') in ['high', 'critical'])

    def test_emits_execution_receipt_after(self):
        """admin-preflight should emit EffectExecutionReceiptV1 after operation."""
        result = subprocess.run(
            [sys.executable, SCRIPT, 'postflight',
             '--operation', 'reembed_missing',
             '--target', 'general',
             '--exit-code', '0',
             '--duration-secs', '5.3'],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['schema'], 'EffectExecutionReceiptV1')
        self.assertEqual(receipt['exit_code'], 0)

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Implement admin-preflight.py**

Core:
- `preflight` subcommand: emits EffectIntentV1 JSON with operation, target, operator, risk_level
  - Risk levels: delete_namespace=critical, reembed_all=high, import_envelope=medium, vacuum=low, reconcile=low
  - For critical/high: requires --confirm flag, otherwise emits block receipt
- `postflight` subcommand: emits EffectExecutionReceiptV1 with operation, exit_code, duration, timestamp
- Both write to claim-ledger if available

**Step 3: Wire into run-server-admin.sh**

Before any admin MCP command, call `admin-preflight.py preflight`. After, call `admin-preflight.py postflight`.

**Step 4: Run tests, commit**

---

### Task C2: Block hard deletes/imports/re-embed without effect receipt

**Objective:** The admin MCP server refuses to run destructive operations unless a valid effect preflight receipt is presented.

**Files:**
- Modify: `shared/scripts/run-server-admin.sh` (enforce preflight receipt requirement)
- Modify: `shared/scripts/admin-preflight.py` (add --verify-receipt flag)
- Create: `tests/test_admin_enforcement.py`

**Step 1: Write failing test**

```python
# tests/test_admin_enforcement.py
import unittest
import json
import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'admin-preflight.py')

class TestAdminEnforcement(unittest.TestCase):
    def test_verify_receipt_accepts_valid(self):
        """admin-preflight verify-receipt should accept a valid preflight receipt."""
        # Generate a preflight receipt
        pre = subprocess.run(
            [sys.executable, SCRIPT, 'preflight',
             '--operation', 'reembed_missing',
             '--target', 'general',
             '--operator', 'test',
             '--confirm'],
            capture_output=True, text=True, timeout=30
        )
        intent = json.loads(pre.stdout)
        # Verify it
        verify = subprocess.run(
            [sys.executable, SCRIPT, 'verify-receipt',
             '--receipt-json', json.dumps(intent)],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(verify.returncode, 0)

    def test_verify_receipt_rejects_missing(self):
        """admin-preflight verify-receipt should reject missing receipt."""
        verify = subprocess.run(
            [sys.executable, SCRIPT, 'verify-receipt',
             '--receipt-json', '{}'],
            capture_output=True, text=True, timeout=30
        )
        self.assertNotEqual(verify.returncode, 0)

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Implement, run tests, commit**

---

### Task C3: Add authority-delegation for operator/admin leases

**Objective:** When multi-agent workers use admin tools, emit authority-delegation leases so the operator can track who authorized what.

**Files:**
- Create: `shared/scripts/authority-delegation.py`
- Create: `tests/test_authority_delegation.py`

**Step 1: Write failing test**

```python
# tests/test_authority_delegation.py
import unittest
import json
import subprocess
import sys
import os
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'authority-delegation.py')

class TestAuthorityDelegation(unittest.TestCase):
    def test_create_lease(self):
        """authority-delegation should create a time-bounded lease."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, SCRIPT, 'create-lease',
                 '--operator', 'josh',
                 '--delegate', 'hermes-agent',
                 '--capabilities', 'reembed,vacuum',
                 '--duration-mins', '30',
                 '--store', os.path.join(tmpdir, 'leases.jsonl')],
                capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            lease = json.loads(result.stdout)
            self.assertEqual(lease['schema'], 'AuthorityLeaseV1')
            self.assertEqual(lease['operator'], 'josh')
            self.assertEqual(lease['delegate'], 'hermes-agent')
            self.assertIn('reembed', lease['capabilities'])
            self.assertIn('expires_at', lease)

    def test_verify_lease_active(self):
        """verify-lease should confirm active lease."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = os.path.join(tmpdir, 'leases.jsonl')
            # Create lease
            subprocess.run(
                [sys.executable, SCRIPT, 'create-lease',
                 '--operator', 'josh', '--delegate', 'hermes-agent',
                 '--capabilities', 'reembed', '--duration-mins', '30',
                 '--store', store],
                capture_output=True, text=True, timeout=30
            )
            # Verify
            result = subprocess.run(
                [sys.executable, SCRIPT, 'verify-lease',
                 '--delegate', 'hermes-agent',
                 '--capability', 'reembed',
                 '--store', store],
                capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, 0)

    def test_verify_lease_expired(self):
        """verify-lease should reject expired lease."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = os.path.join(tmpdir, 'leases.jsonl')
            subprocess.run(
                [sys.executable, SCRIPT, 'create-lease',
                 '--operator', 'josh', '--delegate', 'hermes-agent',
                 '--capabilities', 'reembed', '--duration-mins', '0',
                 '--store', store],
                capture_output=True, text=True, timeout=30
            )
            result = subprocess.run(
                [sys.executable, SCRIPT, 'verify-lease',
                 '--delegate', 'hermes-agent',
                 '--capability', 'reembed',
                 '--store', store],
                capture_output=True, text=True, timeout=30
            )
            self.assertNotEqual(result.returncode, 0)

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Implement, run tests, commit**

---

## Sprint D: Forge/CEA patch verification

### Task D1: Add verify-patch admin workflow script

**Objective:** Add a `verify-patch` admin command that uses typed-patch, sandbox-workspace, check-runner, cea-core, and claim-ledger to verify a patch before apply.

**Files:**
- Create: `shared/scripts/verify-patch.py`
- Create: `tests/test_verify_patch.py`

**Step 1: Write failing test**

```python
# tests/test_verify_patch.py
import unittest
import json
import subprocess
import sys
import os
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'verify-patch.py')

class TestVerifyPatch(unittest.TestCase):
    def test_emits_verification_receipt(self):
        """verify-patch should emit a verification receipt with CEA attribution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal test repo
            repo = os.path.join(tmpdir, 'test-repo')
            os.makedirs(repo)
            with open(os.path.join(repo, 'Cargo.toml'), 'w') as f:
                f.write('[package]\nname = "test"\nversion = "0.1.0"\nedition = "2021"\n')
            os.makedirs(os.path.join(repo, 'src'))
            with open(os.path.join(repo, 'src', 'lib.rs'), 'w') as f:
                f.write('pub fn add(a: i32, b: i32) -> i32 { a + b }\n')

            result = subprocess.run(
                [sys.executable, SCRIPT,
                 '--repo', repo,
                 '--claim', 'add function works correctly',
                 '--check-cmd', 'cargo test',
                 '--out-dir', tmpdir,
                 '--no-memory'],
                capture_output=True, text=True, timeout=120
            )
            # Should produce a receipt even if cargo test is not available in the temp repo
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            receipts = [f for f in os.listdir(tmpdir) if 'verification' in f and f.endswith('.json')]
            self.assertTrue(len(receipts) > 0, "No verification receipt emitted")
            with open(os.path.join(tmpdir, receipts[0])) as f:
                receipt = json.load(f)
            self.assertIn('schema', receipt)
            self.assertIn('check_result', receipt)
            self.assertIn('attribution', receipt)
            self.assertIn('disposition', receipt)

    def test_fails_open_on_missing_dependencies(self):
        """verify-patch should fail open if forge-engine binary is absent."""
        result = subprocess.run(
            [sys.executable, SCRIPT,
             '--repo', '/tmp',
             '--claim', 'test',
             '--check-cmd', 'true',
             '--binary-path', '/nonexistent/forge-engine',
             '--out-dir', '/tmp',
             '--no-memory'],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('forge', result.stderr.lower() + result.stdout.lower())

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Implement verify-patch.py**

Pipeline:
1. Parse: repo path, claim text, check command, out-dir
2. Create sandbox workspace (temp copy of repo)
3. Run check command in sandbox, capture CheckResult
4. If forge-engine binary available:
   a. Build EditOpSignature from any changes
   b. Run cea-core `attribute_effects()` to get AttributionTriple[]
   c. Run cea-core `predict()` for risk prediction
   d. Build CausalGraph update
5. Build verification receipt:
   - schema: `PatchVerificationReceiptV1`
   - check_result (exit_code, stdout, stderr, timings)
   - attribution (triples, risk_flags, confidence)
   - causal_prediction (if available)
   - disposition (promote if check passes, reject if not, quarantine if uncertain)
   - claim
   - trace_ctx (stack-ids)
   - git_commit
   - timestamp
6. Optionally store in claim-ledger and semantic-memory
7. Write to out-dir

**Step 3: Run tests, commit**

---

### Task D2: Add Forge/CEA admin MCP tool path

**Objective:** Expose verify-patch as an admin MCP tool (not daily lean).

**Files:**
- Modify: `hermes/plugin.json` (add forge-admin MCP server entry)
- Create: `shared/scripts/forge-admin-mcp.py` (MCP server wrapper)
- Create: `hermes/scripts/run-forge-admin.sh` (launcher)
- Create: `tests/test_forge_admin_mcp.py`

**Step 1: Write failing test**

```python
# tests/test_forge_admin_mcp.py
import unittest
import json
import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'forge-admin-mcp.py')

class TestForgeAdminMcp(unittest.TestCase):
    def test_lists_tools(self):
        """forge-admin-mcp should list verify-patch and related tools."""
        result = subprocess.run(
            [sys.executable, SCRIPT, '--list-tools'],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        tools = json.loads(result.stdout)
        tool_names = [t['name'] for t in tools]
        self.assertIn('forge_verify_patch', tool_names)
        self.assertIn('forge_get_attribution', tool_names)
        self.assertIn('forge_predict_risk', tool_names)

    def test_tool_descriptions_have_boundaries(self):
        """Each tool description should mention it is admin-only."""
        result = subprocess.run(
            [sys.executable, SCRIPT, '--list-tools'],
            capture_output=True, text=True, timeout=30
        )
        tools = json.loads(result.stdout)
        for tool in tools:
            self.assertIn('admin', tool['description'].lower())

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Implement forge-admin-mcp.py**

A minimal MCP server that exposes:
- `forge_verify_patch` — runs verify-patch.py pipeline
- `forge_get_attribution` — queries CEA graph for attribution data
- `forge_predict_risk` — runs cea-core predict for a given edit signature
- `forge_export_evidence` — exports Forge evidence bundle for claim-ledger

All tools are admin-only, clearly described as patch-verification/release-gate infrastructure.

**Step 3: Add to plugin.json**

```json
"forge-admin": {
  "command": "bash",
  "args": ["scripts/run-forge-admin.sh"]
}
```

**Step 4: Run tests, commit**

---

### Task D3: Forge/CEA standalone extraction preparation

**Objective:** Prepare the Forge crate family for standalone repo extraction and crates.io publication. This is preparation, not the extraction itself.

**Files:**
- Create: `/home/sikmindz/Coding/Libraries/docs/forge-standalone-extraction-plan.md`
- Modify: READMEs for forge-engine, forge-pilot, typed-patch, check-runner, sandbox-workspace, cea-core, cea-store, cea-sqlite, effect-signature, forge-policy, stabilizer-core, mindstate-core (add diagrams, examples, boundaries)

**Step 1: Write the extraction plan document**

Contents:
1. Target repo: `recursiveintell/forge`
2. Crate family: 12 crates (listed above)
3. Dependency chain: cea-core <- cea-store <- cea-sqlite; typed-patch <- forge-engine; check-runner <- forge-engine; etc.
4. Publication order (deps first):
   - Phase 1: typed-patch, effect-signature, forge-policy, stabilizer-core, mindstate-core, cea-core, cea-store, cea-sqlite, check-runner, sandbox-workspace
   - Phase 2: forge-engine (depends on all Phase 1)
   - Phase 3: forge-pilot (depends on forge-engine)
5. README requirements per crate:
   - One-sentence use case
   - "What this crate owns"
   - "What this crate explicitly does not own"
   - Minimal runnable example
   - Architecture or flow diagram
   - Integration map to adjacent crates
   - Claim boundary
6. Dry-run packaging fixes needed (verify `cargo publish --dry-run` for each)
7. Public positioning: "Forge: causal edit attribution and receipt-backed patch verification"
8. Lead line: "Know which agent edit caused which check result."

**Step 2: Upgrade READMEs (highest priority: forge-engine, cea-core, typed-patch, check-runner)**

For each crate, add:
- Architecture diagram (mermaid or ASCII)
- Minimal example
- Non-goals section
- Integration map

**Step 3: Verify dry-run packaging**

```bash
cd /home/sikmindz/Coding/Libraries
for crate in Primitives/typed-patch Primitives/effect-signature Primitives/forge-policy Primitives/stabilizer-core Primitives/mindstate-core Primitives/cea-core Primitives/cea-store Primitives/cea-sqlite Primitives/check-runner Primitives/sandbox-workspace living-memory/living-memory forge-pilot; do
  echo "=== $crate ==="
  cargo publish --dry-run -p $(basename $crate) 2>&1 | tail -5
done
```

Record which crates pass dry-run and which need fixes.

**Step 4: Commit**

---

## Sprint E: trust polish

### Task E1: Promote claim-ledger to shared proof sink

**Objective:** All material plugin operations write to claim-ledger, not just local JSON.

**Files:**
- Modify: `shared/scripts/evidence-workbench.py`
- Modify: `shared/scripts/release-gate-v2.py`
- Modify: `shared/scripts/admin-preflight.py`
- Modify: `shared/scripts/verify-patch.py`
- Modify: `shared/scripts/context-governor-audit.py`
- Modify: `shared/scripts/benchmark-recall.py`
- Create: `tests/test_claim_ledger_integration.py`

**Step 1: Write failing test**

```python
# tests/test_claim_ledger_integration.py
import unittest
import json
import subprocess
import sys
import os

class TestClaimLedgerIntegration(unittest.TestCase):
    def test_release_gate_writes_to_claim_ledger(self):
        """release-gate-v2 should write claim + evidence to claim-ledger if available."""
        # Check that release-gate-v2 has --write-claim-ledger flag
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'release-gate-v2.py'),
             '--help'],
            capture_output=True, text=True, timeout=30
        )
        self.assertIn('--write-claim-ledger', result.stdout)

    def test_verify_patch_writes_to_claim_ledger(self):
        """verify-patch should write verification claim to claim-ledger if available."""
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts', 'verify-patch.py'),
             '--help'],
            capture_output=True, text=True, timeout=30
        )
        self.assertIn('--write-claim-ledger', result.stdout)

if __name__ == '__main__':
    unittest.main()
```

**Step 2: Add --write-claim-ledger flag to all material scripts**

When flag is present and claim-ledger MCP is available:
1. Call `cl_create_claim` with claim text
2. Call `cl_add_evidence` with command receipt / verification receipt
3. Call `cl_judge_support` with judgment (supported/rejected)
4. Call `cl_export_bundle` to get exportable bundle

**Step 3: Run tests, commit**

---

### Task E2: Remove stale public claims and duplicated wrappers

**Objective:** Clean up README/tool-count drift, duplicate host wrappers, and stale claims before any public push.

**Files:**
- Modify: `README.md` (reference generated tool-surface docs, remove hand-maintained counts)
- Modify: `hermes/README.md` (align with generated docs)
- Modify: all host wrapper scripts (move shared logic to shared/scripts, keep host wrappers as 3-line shims)
- Modify: `.gitignore` (add `__pycache__/`)
- Remove or reword any "proves correctness" phrasing

**Step 1: Audit README claims**

- Find all tool count mentions (61, 48, 41, 34, etc.)
- Replace with: "See generated tool-surface docs for current counts per profile"
- Or reference the generated JSON artifact

**Step 2: Audit host wrappers**

For each of Claude/Codex/Hermes:
- Hooks should import from shared/scripts, not duplicate logic
- Scripts should be thin shims (3-5 lines) that set path and call shared

**Step 3: Add .gitignore entries**

```
__pycache__/
*.pyc
_receipts/
```

**Step 4: Search and fix "proves correctness" phrasing**

```bash
grep -ri "proves correctness\|proof of correctness\|guarantees correctness" . --include="*.md" --include="*.py" | grep -v .git
```

Replace with: "proves command execution and boundaries" or "receipt-backed verification"

**Step 5: Commit**

---

## Verification gauntlet

Run after each sprint:

### Sprint A gate

```bash
cd /home/sikmindz/Coding/agent-memory-kits
python -m unittest tests/test_context_governor_audit.py tests/test_tool_surface_docs.py tests/test_recall_admission.py tests/test_benchmark_recall.py -v
python shared/scripts/doctor_core.py --host hermes --receipt /tmp/sprint-a-doctor.json
```

### Sprint B gate

```bash
python -m unittest tests/test_release_gate_v2.py tests/test_doctor_claim_ledger.py tests/test_trace_ids.py -v
python shared/scripts/release-gate-v2.py --claim "Sprint B tests pass" --cmd "python -m unittest tests/test_release_gate_v2.py tests/test_doctor_claim_ledger.py tests/test_trace_ids.py -v" --cwd /home/sikmindz/Coding/agent-memory-kits --no-memory --out-dir /tmp/sprint-b-proof
```

### Sprint C gate

```bash
python -m unittest tests/test_admin_preflight.py tests/test_admin_enforcement.py tests/test_authority_delegation.py -v
python shared/scripts/doctor_core.py --host hermes --deep --receipt /tmp/sprint-c-doctor.json
```

### Sprint D gate

```bash
python -m unittest tests/test_verify_patch.py tests/test_forge_admin_mcp.py -v
python shared/scripts/verify-patch.py --repo /home/sikmindz/Coding/agent-memory-kits --claim "Forge verify-patch works" --check-cmd "python -m unittest tests/test_verify_patch.py -v" --out-dir /tmp/sprint-d-proof --no-memory
```

### Sprint E gate

```bash
python -m unittest tests/test_claim_ledger_integration.py -v
python -m json.tool hermes/plugin.json >/dev/null
python -m py_compile hermes/hooks/*.py hermes/scripts/*.py shared/scripts/*.py codex/plugins/semantic-memory/hooks/*.py codex/plugins/semantic-memory/scripts/*.py claude/plugins/semantic-memory/scripts/*.py
grep -ri "proves correctness" . --include="*.md" --include="*.py" | grep -v .git || echo "No false correctness claims found"
```

### Full gauntlet (after all sprints)

```bash
cd /home/sikmindz/Coding/agent-memory-kits
python -m json.tool hermes/plugin.json >/dev/null
python -m py_compile hermes/hooks/*.py hermes/scripts/*.py shared/scripts/*.py codex/plugins/semantic-memory/hooks/*.py codex/plugins/semantic-memory/scripts/*.py claude/plugins/semantic-memory/scripts/*.py
python -m unittest discover tests/ -v
python shared/scripts/doctor_core.py --host hermes --deep --receipt /tmp/full-gauntlet-doctor.json
python shared/scripts/release-gate-v2.py --claim "Full plugin/MCP ROI implementation passes" --cmd "python -m unittest discover tests/ -v" --cwd /home/sikmindz/Coding/agent-memory-kits --no-memory --out-dir /tmp/full-gauntlet-proof
```

---

## Claim boundary

After Sprint A only: "Context-governor audit surface, tool-surface generation, recall admission gating, and receipt-bench benchmark command are implemented with targeted tests."

After Sprints A+B: "Plus: Evidence Workbench v2 with claim-ledger integration, doctor claim-ledger verification, and stack-ids trace spine."

After Sprints A+B+C: "Plus: admin action preflight with effect-runtime/policy/control and authority-delegation leases."

After Sprints A+B+C+D: "Plus: Forge/CEA patch verification admin workflow and MCP tool path. Standalone extraction preparation complete."

After all sprints: "The agent-memory-kits plugin stack is an admission-controlled, receipt-backed, side-effect-aware, evidence-producing memory runtime. Forge/CEA patch verification is available as an admin workflow. Standalone Forge repo extraction is prepared but not yet executed."

Do NOT claim:
- "The plugin stack proves correctness" — it proves command execution and boundaries
- "Forge is published" — until crates.io dry-runs pass and actual publication happens
- "Memory recall is proof" — keep "discovery, not proof" visible
- "All tools are in daily MCP" — admin/forge tools are deliberately separate

---

## Hard no list

- No semantic-memory-mcp on ESP32
- No Forge/CEA in daily lean MCP profile
- No new plugin claims before Sprint A truth-floor audit passes
- No daily-profile MCP bloat with release/admin/forge tools
- No public ESP32 performance claim unless backed by receipt + promoted disposition
- No hand-maintained tool counts in README
- No "proves correctness" phrasing
- No graph-heavy recall by default for simple lookups
- No rewriting all hooks in Rust immediately (canonicalize JSON schemas first)
- No Forge standalone repo extraction until Sprint D integration is receipt-verified

---

## One-line verdict

Use the already-written governance crates as the plugin stack's missing control plane: context-governor high_roi audits, llm-tool-runtime/stack-ids receipts, verification/claim-ledger proof packets, admission-time recall gating, and Forge/CEA as a separate admin patch-verification path. That turns the plugins from "memory add-on" into an operator-grade evidence system with a standalone Forge product extraction ready to ship.