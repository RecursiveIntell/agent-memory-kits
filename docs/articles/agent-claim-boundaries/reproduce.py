#!/usr/bin/env python3
"""Capture and verify three bounded, local observations of a pinned public script.

This is a case-study fixture, not a release gate, sandbox, security proof, or
independent reproduction.  It never writes to semantic memory or ClaimLedger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

SOURCE_COMMIT = "77f8b6829e5fc09460c70553413cd0bd5560a8be"
SOURCE_REL = "shared/scripts/evidence-workbench.py"
SOURCE_SHA256 = "f2d0c8555b143fb770ca3b021549b8593697ea30ea9a3bdf59eef7fbc0aec5ea"
BOUNDARY = "Command receipts prove the listed gates ran with the captured exit codes; they do not prove untested behavior."
BROAD = "The entire test suite passed and the software is production ready"
CASES = (
    ("broad-pass", BROAD, "true", 0, "promote"),
    ("narrow-pass", "The supplied true command exited zero", "true", 0, "promote"),
    ("broad-fail", BROAD, "false", 1, "reject"),
)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def source_identity() -> Path:
    source = ROOT / SOURCE_REL
    require(source.is_file(), f"missing source: {SOURCE_REL}")
    require(sha(source.read_bytes()) == SOURCE_SHA256, "active source differs from pinned source")
    committed = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_REL}"],
        cwd=ROOT, capture_output=True, check=True, timeout=15,
    ).stdout
    require(sha(committed) == SOURCE_SHA256, "pinned Git blob differs from source hash")
    return source


def check_case(name: str, claim: str, command: str, exit_code: int,
               disposition: str, wrapper: dict, packet: dict) -> None:
    require(wrapper["case"] == name, f"{name}: wrong case")
    require(wrapper["command"] == command, f"{name}: wrong command")
    require(wrapper["claim"] == claim, f"{name}: wrong claim")
    require(wrapper["process_exit_code"] == exit_code, f"{name}: wrong process exit")
    require(packet["schema"] == "AgentEvidenceWorkbenchProofPacketV1", f"{name}: wrong schema")
    require(packet["claim"] == claim, f"{name}: packet claim mismatch")
    require(packet["disposition"] == disposition, f"{name}: disposition mismatch")
    require(packet["claim_boundary"] == BOUNDARY, f"{name}: missing explicit boundary")
    require(len(packet["commands"]) == 1, f"{name}: command count mismatch")
    row = packet["commands"][0]
    require(row["command"] == command, f"{name}: recorded command mismatch")
    require(row["exit_code"] == (0 if command == "true" else 1), f"{name}: command exit mismatch")
    require(row["timed_out"] is False, f"{name}: timed out")
    require(row["stdout_sha256"] == sha(b""), f"{name}: unexpected stdout")
    require(row["stderr_sha256"] == sha(b""), f"{name}: unexpected stderr")
    require(row["combined_sha256"] == sha(b"\n"), f"{name}: combined-output hash mismatch")
    require(packet["evidence_refs"] == ["sha256:" + sha(b"\n")], f"{name}: evidence ref mismatch")
    claimed_digest = packet["proof_packet_sha256"]
    unsigned_packet = {k: v for k, v in packet.items() if k != "proof_packet_sha256"}
    recomputed = sha(json.dumps(unsigned_packet, sort_keys=True).encode("utf-8"))
    require(recomputed == claimed_digest, f"{name}: internal packet hash mismatch")
    printed = json.loads(wrapper["stdout"])
    require(printed["ok"] == (exit_code == 0), f"{name}: printed ok mismatch")
    require(printed["disposition"] == disposition, f"{name}: printed disposition mismatch")
    require(printed["packet_sha256"] == claimed_digest, f"{name}: printed digest mismatch")
    require(wrapper["stderr"] == "", f"{name}: unexpected stderr")
    require("semantic_memory_result" not in packet and "claim_ledger_result" not in packet,
            f"{name}: unexpected external-write field")


def capture(out: Path) -> dict:
    source = source_identity()
    require(not out.exists() or not list(out.iterdir()), "refusing to overwrite existing receipt files")
    out.mkdir(parents=True, exist_ok=True)
    packets = out / "packets"
    packets.mkdir()
    wrappers = []
    # Keep all effects in a disposable, neutral-named /tmp directory.
    with tempfile.TemporaryDirectory(prefix="agent-claim-fixture-", dir="/tmp") as tmp:
        base = Path(tmp)
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(base),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        for name, claim, command, expected_exit, expected_disposition in CASES:
            cwd = base / name
            cwd.mkdir()
            emitted = cwd / "emitted"
            process = subprocess.run(
                [sys.executable, str(source), "--claim", claim, "--cmd", command,
                 "--cwd", str(cwd), "--out-dir", str(emitted), "--no-memory"],
                cwd=cwd, env=environment, capture_output=True, text=True, timeout=20,
            )
            outputs = list(emitted.glob("evidence-workbench-*.json"))
            require(len(outputs) == 1, f"{name}: expected exactly one emitted packet")
            raw = outputs[0].read_bytes()
            stored = packets / f"{name}.json"
            stored.write_bytes(raw)  # Exact bytes, no redaction or transformation.
            wrapper = {
                "case": name,
                "claim": claim,
                "command": command,
                "invocation": ["python3", SOURCE_REL, "--claim", claim,
                               "--cmd", command, "--cwd", "<disposable-case-dir>",
                               "--out-dir", "<disposable-case-dir>/emitted", "--no-memory"],
                "process_exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "stdout_sha256": sha(process.stdout.encode("utf-8")),
                "stderr_sha256": sha(process.stderr.encode("utf-8")),
                "packet": f"packets/{name}.json",
                "packet_sha256": sha(raw),
            }
            check_case(name, claim, command, expected_exit, expected_disposition,
                       wrapper, json.loads(raw))
            wrappers.append(wrapper)
    record = {
        "schema": "AgentClaimCaseStudyCaptureV1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": SOURCE_COMMIT,
        "source_path": SOURCE_REL,
        "source_sha256": SOURCE_SHA256,
        "fixture_sha256": sha(Path(__file__).read_bytes()),
        "python_version": platform.python_version(),
        "os_family": platform.system(),
        "environment_boundary": "Disposable local /tmp; --no-memory; no --write-claim-ledger; no remote model/provider call",
        "cases": wrappers,
        "limitations": [
            "Captured by the article author, not independently reproduced",
            "A passing command demonstrates its own outcome, not coverage or semantic support",
            "Packet digest is a local integrity check, not an external signature or runtime attestation",
        ],
    }
    (out / "capture.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    verify(out)
    return record


def verify(out: Path) -> dict:
    source_identity()
    record = json.loads((out / "capture.json").read_text())
    require(record["schema"] == "AgentClaimCaseStudyCaptureV1", "wrong capture schema")
    require(record["source_commit"] == SOURCE_COMMIT, "wrong source commit")
    require(record["source_path"] == SOURCE_REL, "wrong source path")
    require(record["source_sha256"] == SOURCE_SHA256, "wrong source hash")
    require(record["fixture_sha256"] == sha(Path(__file__).read_bytes()), "fixture changed since capture")
    require(len(record["cases"]) == len(CASES), "case count mismatch")
    for expected, wrapper in zip(CASES, record["cases"], strict=True):
        name, claim, command, exit_code, disposition = expected
        require(wrapper["packet"] == f"packets/{name}.json", f"{name}: unexpected packet path")
        packet_bytes = (out / wrapper["packet"]).read_bytes()
        require(sha(packet_bytes) == wrapper["packet_sha256"], f"{name}: packet bytes changed")
        require(sha(wrapper["stdout"].encode("utf-8")) == wrapper["stdout_sha256"],
                f"{name}: stdout changed")
        require(sha(wrapper["stderr"].encode("utf-8")) == wrapper["stderr_sha256"],
                f"{name}: stderr changed")
        check_case(name, claim, command, exit_code, disposition,
                   wrapper, json.loads(packet_bytes))
    return {"status": "PASS", "cases": [x["case"] for x in record["cases"]],
            "source_commit": SOURCE_COMMIT, "source_sha256": SOURCE_SHA256}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "verify"))
    parser.add_argument("--out-dir", type=Path, default=HERE / "receipts")
    args = parser.parse_args()
    try:
        result = capture(args.out_dir) if args.action == "capture" else verify(args.out_dir)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.action == "capture":
        print(json.dumps({"status": "CAPTURED_AND_VERIFIED",
                          "cases": [x["case"] for x in result["cases"]],
                          "source_commit": SOURCE_COMMIT}, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
