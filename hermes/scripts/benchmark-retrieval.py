#!/usr/bin/env python3
"""Run sm-bench against the semantic-memory warm HTTP server and store the receipt."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))
from http_auth import resolve_http_token

OUTDIR = Path.home() / ".local/share/semantic-memory-agent-kits/receipts"
DEFAULT_FIXTURES = Path.home() / ".local/share/semantic-memory-agent-kits/fixtures"


def resolve_smbench() -> str | None:
    env = os.environ.get("SM_BENCH_BIN")
    if env and os.access(os.path.expanduser(env), os.X_OK):
        return os.path.expanduser(env)
    for c in (Path.home()/".local/bin/sm-bench", Path.home()/"Coding/Libraries/target/release/sm-bench"):
        if c.exists() and os.access(c, os.X_OK): return str(c)
    return shutil.which("sm-bench")


def sanitized_child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("SEMANTIC_MEMORY_HTTP_TOKEN", None)
    env.pop("SM_BENCH_HTTP_AUTH_TOKEN", None)
    return env


def supports_http_auth(binary: str) -> bool:
    """Refuse benchmark binaries that would silently send unauthenticated HTTP."""
    try:
        help_output = subprocess.run(
            [binary, "--help"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
            env=sanitized_child_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "--http-auth-token-file" in f"{help_output.stdout}\n{help_output.stderr}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run sm-bench retrieval quality benchmark and store receipt.")
    ap.add_argument("--server-url", default=os.environ.get("SEMANTIC_MEMORY_HTTP_URL", f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"))
    ap.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES))
    ap.add_argument("--fixtures-file", default=None)
    ap.add_argument("--suite-name", default=None)
    ap.add_argument("--output-dir", default=str(OUTDIR))
    ap.add_argument("--compare", default=None)
    args = ap.parse_args()
    token = resolve_http_token()
    if not token:
        raise SystemExit(
            "Warm HTTP benchmarking requires SEMANTIC_MEMORY_HTTP_TOKEN, "
            "SEMANTIC_MEMORY_HTTP_TOKEN_FILE, or ~/.hermes/semantic-memory-http-1739.token."
        )
    binary = resolve_smbench()
    if not binary:
        raise SystemExit("sm-bench binary not found. Build with: cargo build --features sm-adapter --bin sm-bench")
    if not supports_http_auth(binary):
        raise SystemExit("sm-bench does not support authenticated token input; upgrade to a Bearer-auth-capable sm-bench before benchmarking warm HTTP.")
    out_dir = Path(args.output_dir).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir = Path(args.fixtures_dir).expanduser()
    cmd = [binary, "--server-url", args.server_url, "--output-dir", str(out_dir)]
    if args.fixtures_file:
        cmd.extend(["--fixtures-file", str(args.fixtures_file)])
    elif fixtures_dir.exists():
        cmd.extend(["--fixtures-dir", str(fixtures_dir)])
    else:
        # Create a minimal fixture if none exist
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        fixture = fixtures_dir / "basic.jsonl"
        if not fixture.exists():
            fixture.write_text(json.dumps({"query": "semantic memory plugin hooks", "expected_namespaces": ["infrastructure"], "expected_top_hit_contains": "semantic-memory"}) + "\n", encoding="utf-8")
        cmd.extend(["--fixtures-dir", str(fixtures_dir)])
    if args.suite_name: cmd.extend(["--suite-name", args.suite_name])
    if args.compare: cmd.extend(["--compare", str(args.compare)])
    token_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix="sm-bench-token-", delete=False
        ) as token_file:
            token_file.write(token + "\n")
            token_path = Path(token_file.name)
        token_path.chmod(0o600)
        cmd.extend(["--http-auth-token-file", str(token_path)])
        print(f"Running: {' '.join(cmd)}")
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
            env=sanitized_child_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"sm-bench execution failed: {error}") from error
    finally:
        if token_path is not None:
            token_path.unlink(missing_ok=True)
    print(proc.stdout.replace(token, "<redacted>"))
    if proc.stderr: print(proc.stderr.replace(token, "<redacted>"), file=sys.stderr)
    # Find the receipt file
    receipts = sorted(out_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if receipts:
        print(f"\nReceipt: {receipts[0]}")
    return proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())
