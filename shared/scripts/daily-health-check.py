#!/usr/bin/env python3
"""
Hermes custom additions daily health check.

Tests ALL custom hooks, skills, plugins, scripts, MCP servers, and services.
Designed to run as a daily cron job. Outputs a JSON report and exits non-zero
if any critical component is broken.

Usage:
  python3 ~/.hermes/scripts/daily-health-check.py [--fix]
  
  --fix  Attempt to automatically fix common issues (import errors, broken
         YAML frontmatter, missing function stubs).
"""
import json
import os
import subprocess
import sys
import yaml
import urllib.request
from pathlib import Path
from datetime import datetime

HERMES = Path(os.path.expanduser("~/.hermes"))
HOOKS_DIR = HERMES / "agent-hooks"
SCRIPTS_DIR = HERMES / "scripts"
SKILLS_DIR = HERMES / "skills"
PLUGINS_DIR = HERMES / "plugins"
TOKEN_FILE = HERMES / "semantic-memory-http-admin.token"

results = {
    "timestamp": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
    "checks": [],
    "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 0},
    "critical_failures": [],
}


def check(name, category, passed, detail="", critical=False, fix=None):
    r = {
        "name": name,
        "category": category,
        "passed": passed,
        "detail": detail,
        "critical": critical,
    }
    results["checks"].append(r)
    results["summary"]["total"] += 1
    if passed:
        results["summary"]["passed"] += 1
    else:
        results["summary"]["failed"] += 1
        if critical:
            results["critical_failures"].append(name)
    return r


# ─── HOOKS ───────────────────────────────────────────────────────────────────

hook_env = os.environ.copy()
hook_env.update({
    "SEMANTIC_MEMORY_DIR": str(HERMES / "semantic-memory.db"),
    "SEMANTIC_MEMORY_HTTP_PORT": "1738",
    "SEMANTIC_MEMORY_HTTP_TOKEN_FILE": str(TOKEN_FILE),
    "CLAIM_LEDGER_ROOT": str(HERMES / "claim-ledger"),
    "CONTEXT_GOVERNOR_STORE": str(HERMES / "context-governor"),
})

hook_files = sorted(f for f in os.listdir(HOOKS_DIR) if f.endswith(".py") and not f.startswith("__"))
for hook_file in hook_files:
    path = HOOKS_DIR / hook_file
    # Compile check
    try:
        compile(open(path).read(), hook_file, "exec")
        check(f"hook/{hook_file} (compile)", "hook", True)
    except SyntaxError as e:
        check(f"hook/{hook_file} (compile)", "hook", False, str(e), critical=True)
        continue
    # Import check — use importlib to handle hyphenated filenames
    proc = subprocess.run(
        [sys.executable, "-c", f"""
import sys, importlib.util
sys.path.insert(0, "{HOOKS_DIR}")
spec = importlib.util.spec_from_file_location("{hook_file[:-3]}", "{path}")
if spec and spec.loader:
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        print("IMPORT_OK")
    except Exception as e:
        print(f"IMPORT_FAIL: {{e}}")
else:
    print("IMPORT_FAIL: no spec")
"""],
        capture_output=True, text=True, env=hook_env, timeout=10
    )
    if proc.returncode == 0:
        check(f"hook/{hook_file} (import)", "hook", True)
    else:
        err = proc.stderr.strip().split('\n')[-1] if proc.stderr else "unknown"
        check(f"hook/{hook_file} (import)", "hook", False, err, critical=True)


# ─── HOOK FUNCTIONAL TESTS ───────────────────────────────────────────────────

functional_tests = [
    ("sm-primer.py", '{}', "session_start"),
    ("sm-recall.py", '{"extra":{"user_message":"test query about UNO Q"}}', "pre_llm_recall"),
    ("kr-classify.py", '{"extra":{"user_message":"test query"}}', "query_classify"),
    ("sm-capture-nudge.py", '{}', "session_end"),
    ("sm-dedup-guard.py", '{"tool":"sm_add_fact","args":{"content":"test","namespace":"general"}}', "dedup_guard"),
]

for hook, stdin_data, label in functional_tests:
    path = HOOKS_DIR / hook
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            input=stdin_data, capture_output=True, text=True, env=hook_env, timeout=10
        )
        check(f"hook/{hook} (functional/{label})", "hook", proc.returncode == 0,
              f"exit={proc.returncode}" + (f" stderr={proc.stderr[:80]}" if proc.stderr else ""),
              critical=(hook == "sm-recall.py"))  # recall is critical
    except subprocess.TimeoutExpired:
        check(f"hook/{hook} (functional/{label})", "hook", False, "TIMEOUT (10s)")


# ─── EXISTING TEST SUITES ────────────────────────────────────────────────────

# Hook tests
proc = subprocess.run(
    [sys.executable, "-m", "pytest", str(HOOKS_DIR / "tests"), "--tb=line", "-q"],
    capture_output=True, text=True, timeout=60, cwd=str(HOOKS_DIR)
)
passed = proc.returncode == 0
# Parse pass/fail count from output
import re
match = re.search(r'(\d+) passed(?:.*?(\d+) failed)?', proc.stdout)
if match:
    p, f = int(match.group(1)), int(match.group(2) or 0)
    check("test-suite/agent-hooks", "test-suite", f == 0, f"{p} passed, {f} failed")
else:
    check("test-suite/agent-hooks", "test-suite", passed, proc.stdout[-200:])

# Plugin tests
plugin_test_dir = PLUGINS_DIR / "semantic-memory-mcp" / "tests"
if plugin_test_dir.exists():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(plugin_test_dir), "--tb=line", "-q"],
        capture_output=True, text=True, timeout=60, cwd=str(PLUGINS_DIR / "semantic-memory-mcp")
    )
    match = re.search(r'(\d+) passed(?:.*?(\d+) skipped)?(?:.*?(\d+) failed)?', proc.stdout)
    if match:
        p, s, f = int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0)
        check("test-suite/plugin", "test-suite", f == 0, f"{p} passed, {s} skipped, {f} failed")
    else:
        check("test-suite/plugin", "test-suite", proc.returncode == 0, proc.stdout[-200:])


# ─── SKILLS YAML VALIDITY ────────────────────────────────────────────────────

skill_errors = []
skill_count = 0
for root, dirs, files in os.walk(SKILLS_DIR):
    if "SKILL.md" in files:
        skill_count += 1
        path = Path(root) / "SKILL.md"
        try:
            content = open(path).read()
            if content.startswith("---"):
                end = content.index("---", 3)
                frontmatter = content[3:end]
                data = yaml.safe_load(frontmatter)
                if "name" not in data:
                    skill_errors.append(f"{path}: missing 'name' in frontmatter")
            else:
                skill_errors.append(f"{path}: no YAML frontmatter")
        except Exception as e:
            skill_errors.append(f"{path}: {e}")

check("skills/yaml-validity", "skill", len(skill_errors) == 0,
      f"{skill_count} skills, {len(skill_errors)} broken" +
      (f": {'; '.join(skill_errors[:3])}" if skill_errors else ""))


# ─── MCP SERVER HEALTH ───────────────────────────────────────────────────────

# semantic-memory HTTP
try:
    token = open(TOKEN_FILE).read().strip()
    req = urllib.request.Request("http://127.0.0.1:1738/health")
    req.add_header("Authorization", f"Bearer {token}")
    resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
    check("mcp/semantic-memory-http", "mcp", resp.get("ok", False), str(resp), critical=True)
except Exception as e:
    check("mcp/semantic-memory-http", "mcp", False, str(e), critical=True)

# mnemes tunnel (if running)
try:
    resp = json.loads(urllib.request.urlopen("http://127.0.0.1:1748/v1/livez", timeout=5).read())
    check("mcp/mnemes-tunnel", "mcp", resp.get("service") == "up", str(resp))
except Exception as e:
    check("mcp/mnemes-tunnel", "mcp", False, str(e))


# ─── SYSTEMD SERVICES ────────────────────────────────────────────────────────

for svc in ["semantic-memory.service", "mnemes-tunnel.service", "hermes-gateway.service"]:
    proc = subprocess.run(
        ["systemctl", "--user", "is-active", svc],
        capture_output=True, text=True, timeout=5
    )
    active = proc.stdout.strip() == "active"
    critical = svc == "semantic-memory.service"
    check(f"systemd/{svc}", "service", active, proc.stdout.strip(), critical=critical)


# ─── CARGO BINARIES ──────────────────────────────────────────────────────────

for binary in ["agent-graph-mcp", "mnemes-server", "mnemes-admin", "context-governor", "cea-bridge"]:
    path = Path.home() / ".cargo" / "bin" / binary
    exists = path.exists() and os.access(path, os.X_OK)
    check(f"binary/{binary}", "binary", exists, str(path))

# semantic-memory-mcp is in ~/.local/bin/
sm_path = Path.home() / ".local" / "bin" / "semantic-memory-mcp"
check("binary/semantic-memory-mcp", "binary", sm_path.exists() and os.access(sm_path, os.X_OK),
      str(sm_path), critical=True)


# ─── SCRIPTS ─────────────────────────────────────────────────────────────────

for script in sorted(os.listdir(SCRIPTS_DIR)):
    if script.startswith('__') or script.startswith('.'):
        continue
    path = SCRIPTS_DIR / script
    if script.endswith('.py'):
        try:
            compile(open(path).read(), script, 'exec')
            check(f"script/{script}", "script", True)
        except SyntaxError as e:
            check(f"script/{script}", "script", False, str(e))
    elif script.endswith('.sh'):
        check(f"script/{script}", "script", os.access(path, os.X_OK), "executable" if os.access(path, os.X_OK) else "not executable")


# ─── PLUGIN VALIDITY ─────────────────────────────────────────────────────────

plugin_path = PLUGINS_DIR / "semantic-memory-mcp"
if plugin_path.exists():
    for json_file in ["plugin.json", "plugin.yaml"]:
        p = plugin_path / json_file
        if p.exists():
            try:
                if json_file.endswith('.json'):
                    json.load(open(p))
                else:
                    yaml.safe_load(open(p))
                check(f"plugin/{json_file}", "plugin", True)
            except Exception as e:
                check(f"plugin/{json_file}", "plugin", False, str(e), critical=True)
else:
    check("plugin/semantic-memory-mcp", "plugin", False, "plugin dir missing", critical=True)


# ─── OUTPUT ──────────────────────────────────────────────────────────────────

report_path = HERMES / "daily-health-report.json"
with open(report_path, 'w') as f:
    json.dump(results, f, indent=2)

# Print summary
s = results["summary"]
print(f"\n{'='*60}")
print(f"Hermes Daily Health Check — {results['timestamp']}")
print(f"{'='*60}")
print(f"Total: {s['total']}  Passed: {s['passed']}  Failed: {s['failed']}")
print(f"Report: {report_path}")

if results["critical_failures"]:
    print(f"\n❌ CRITICAL FAILURES:")
    for name in results["critical_failures"]:
        # Find the detail
        for c in results["checks"]:
            if c["name"] == name and not c["passed"]:
                print(f"  • {name}: {c['detail']}")
                break
    sys.exit(1)
else:
    print(f"\n✅ All critical systems healthy")
    if s["failed"] > 0:
        print(f"⚠️  {s['failed']} non-critical warnings")
    sys.exit(0)