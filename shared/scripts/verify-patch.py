#!/usr/bin/env python3
"""verify-patch.py — Forge/CEA patch verification surface.

Creates a PatchVerificationReceiptV1 by:
  1. Copying the repo into a temp sandbox (excluding .git, target/, node_modules/)
  2. Running the user-specified --check-cmd in that sandbox
  3. If the forge-engine binary is available, invoking it for CEA attribution;
     otherwise falling back to a pure-Python receipt builder.
  4. Writing the receipt to --out-dir and (optionally) a summary to semantic-memory.

Fail-open: if the forge-engine binary is missing, the script still works.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# --- trace_ids import -------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from trace_ids import generate_trace_id  # noqa: E402
try:  # noqa: E402
    from license_client import require_license_state
except Exception:  # noqa: E402
    require_license_state = None  # type: ignore


# --- constants --------------------------------------------------------------
SCHEMA = "PatchVerificationReceiptV1"
CLAIM_BOUNDARY = (
    "Receipt proves command execution and exit code; "
    "it does not prove total correctness or untested behavior."
)
DEFAULT_BINARIES = [
    Path.home() / ".cargo" / "bin" / "forge-pilot",
    Path.home() / ".cargo" / "bin" / "forge-engine",
]
EXCLUDE_DIRS = {".git", "target", "node_modules"}
TIMEOUT_SECS = 300


# --- helpers ----------------------------------------------------------------
def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8", "replace")).hexdigest()


def _git_head(repo: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _copy_sandbox(repo: Path, sandbox: Path) -> None:
    """Copy repo → sandbox, skipping EXCLUDE_DIRS."""
    for item in repo.iterdir():
        if item.name in EXCLUDE_DIRS:
            continue
        dst = sandbox / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=False, symlinks=True)
        else:
            shutil.copy2(item, dst)


def _run_check(check_cmd: str, sandbox: Path, timeout: int = TIMEOUT_SECS) -> dict:
    """Run *check_cmd* inside *sandbox* and return a result dict."""
    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            check_cmd,
            shell=True,
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        exit_code = -1
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else ""
        stderr = (e.stderr or "") if isinstance(e.stderr, str) else ""
    except Exception as e:
        exit_code = -2
        stdout = ""
        stderr = str(e)
    duration = round(time.monotonic() - start, 4)

    return {
        "command": check_cmd,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout_sha256": _sha256_hex(stdout),
        "stderr_sha256": _sha256_hex(stderr),
        "duration_secs": duration,
    }


def _resolve_forge_binary(binary_arg: str) -> Path | None:
    """Resolve a requested Forge binary.

    `auto` prefers forge-pilot, then forge-engine, then `RI_FORGE_BINARY` if set.
    Explicit paths preserve backwards compatibility and may intentionally be
    nonexistent to force fallback-mode tests.
    """
    if binary_arg != "auto":
        return Path(binary_arg)
    env_binary = os.environ.get("RI_FORGE_BINARY")
    candidates = ([Path(env_binary)] if env_binary else []) + DEFAULT_BINARIES
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _try_forge_engine(binary: Path | None, sandbox: Path, check_result: dict) -> dict | None:
    """If a Forge binary exists and is executable, call it and return
    an attribution dict.  Return *None* on any failure (caller falls back)."""
    if binary is None or not binary.exists() or not os.access(binary, os.X_OK):
        return None
    try:
        proc = subprocess.run(
            [str(binary), "--sandbox", str(sandbox), "--json"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECS,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            return {
                "available": True,
                "engine": binary.name,
                "cea": data.get("cea", {}),
                "raw": data,
            }
    except Exception:
        pass
    return None


def _semantic_memory_base_url() -> str:
    return os.environ.get("SEMANTIC_MEMORY_HTTP_URL") or f"http://127.0.0.1:{os.environ.get('SEMANTIC_MEMORY_HTTP_PORT', '1739')}"


def _write_semantic_memory(claim: str, receipt: dict) -> bool:
    """Best-effort POST to the configured semantic-memory HTTP /add endpoint."""
    try:
        import urllib.request

        payload = json.dumps({
            "content": f"[verify-patch] {claim} — disposition={receipt['disposition']}",
            "namespace": "forge-verify",
            "memory_kind": "observation",
            "source": "verify-patch.py",
            "evidence_refs": [receipt["trace_id"]],
        }).encode("utf-8")
        req = urllib.request.Request(
            _semantic_memory_base_url().rstrip("/") + "/add",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def _build_receipt(
    *,
    claim: str,
    check_result: dict,
    attribution: dict,
    git_commit: str,
    trace_id: str,
    timestamp: str,
) -> dict:
    if check_result["timed_out"]:
        disposition = "quarantine"
    elif check_result["exit_code"] == 0:
        disposition = "promote"
    else:
        disposition = "reject"

    return {
        "schema": SCHEMA,
        "trace_id": trace_id,
        "claim": claim,
        "check_result": check_result,
        "attribution": attribution,
        "disposition": disposition,
        "git_commit": git_commit,
        "timestamp": timestamp,
        "claim_boundary": CLAIM_BOUNDARY,
    }


# --- main -------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Forge/CEA patch verification — produces a PatchVerificationReceiptV1"
    )
    parser.add_argument("--repo", required=True, help="Path to the repo to verify")
    parser.add_argument("--claim", required=True, help="Claim about the patch")
    parser.add_argument("--check-cmd", required=True, help="Command to run for verification")
    parser.add_argument("--out-dir", required=True, help="Where to write the receipt JSON")
    parser.add_argument("--no-memory", action="store_true", help="Skip semantic-memory write")
    parser.add_argument("--write-claim-ledger", action="store_true", help="Write verification claim to claim-ledger MCP if available")
    parser.add_argument(
        "--binary-path",
        default="auto",
        help="Path to Forge binary, or 'auto' to prefer RI_FORGE_BINARY, forge-pilot, then forge-engine",
    )
    args = parser.parse_args(argv)

    if require_license_state is not None:
        license_state = require_license_state("forge-admin")
    else:
        license_state = {
            "schema": "RecursiveIntellProLicenseStateV1",
            "feature": "forge-admin",
            "trusted": False,
            "blocked": False,
            "skipped": False,
            "reason": "license client unavailable",
            "token": None,
        }

    repo = Path(args.repo).resolve()
    out_dir = Path(args.out_dir).resolve()
    binary = _resolve_forge_binary(args.binary_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create sandbox
    sandbox_parent = tempfile.mkdtemp(prefix="forge-verify-")
    sandbox = Path(sandbox_parent) / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)

    try:
        # 2. Copy repo → sandbox
        _copy_sandbox(repo, sandbox)

        # 3. Run check-cmd
        check_result = _run_check(args.check_cmd, sandbox)

        # 4. Try Forge binary; fall back to pure-Python
        cea = _try_forge_engine(binary, sandbox, check_result)
        if cea is None:
            if binary is None:
                print(
                    "no Forge binary found (checked RI_FORGE_BINARY, forge-pilot, forge-engine) — using pure-Python fallback",
                    file=sys.stderr,
                )
            elif not binary.exists():
                print(
                    f"Forge binary not found at {binary} — using pure-Python fallback",
                    file=sys.stderr,
                )
            attribution = {
                "available": False,
                "reason": "Forge binary not available",
            }
        else:
            attribution = cea

        # 5. Build receipt
        trace_id = generate_trace_id("forge-verify")
        timestamp = datetime.now(timezone.utc).isoformat()
        git_commit = _git_head(repo)

        receipt = _build_receipt(
            claim=args.claim,
            check_result=check_result,
            attribution=attribution,
            git_commit=git_commit,
            trace_id=trace_id,
            timestamp=timestamp,
        )
        receipt["license_state"] = license_state

        # 6. Semantic-memory write (best-effort, unless --no-memory)
        if not args.no_memory:
            _write_semantic_memory(args.claim, receipt)

        # 7. Write receipt file
        safe_ts = timestamp.replace(":", "-").replace("+", "-")
        receipt_path = out_dir / f"verify-patch-{safe_ts}.json"
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

        # 8. Print JSON summary
        ok = receipt["disposition"] == "promote"
        summary = {
            "ok": ok,
            "disposition": receipt["disposition"],
            "receipt": str(receipt_path),
        }
        print(json.dumps(summary))

        # 9. Exit code
        return 0 if ok else 1

    finally:
        # Clean up sandbox
        shutil.rmtree(sandbox_parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())