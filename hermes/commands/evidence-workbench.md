# /evidence-workbench

Run command gates and emit an Agent Evidence Workbench proof packet.

Use when you are about to claim work is done, or when a material release/readiness claim needs receipts.

Example:

```bash
python3 scripts/evidence-workbench.py \
  --claim "agent-memory-kits validation passes" \
  --cwd /home/sikmindz/Coding/agent-memory-kits \
  --cmd "python -m json.tool hermes/plugin.json >/dev/null" \
  --cmd "bash scripts/validate-all-kits.sh"
```

Rules:
- `disposition=promote` only when every command exits 0.
- `disposition=reject` on any failing or timed-out command.
- The packet records command, cwd, exit code, stdout/stderr digests, previews, evidence refs, and a claim boundary.
- Do not claim done unless the relevant proof packet promotes.
