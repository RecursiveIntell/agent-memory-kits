#!/usr/bin/env python3
"""context-governor-audit.py — expose high_roi.rs audit functions as CLI.

Subcommands:
  audit-tool-surface   — audit MCP tool descriptions for split-instruction/selection risks
  eval-governed-memory  — evaluate memory governance cases
  eval-rag-leakage      — evaluate retrieval leakage-free RAG
  screen-conflicts      — screen knowledge claims for conflicts
  select-route          — select retrieval route for a query

All subcommands fail open (exit 0 with stderr message) if the context-governor
binary is absent or errors.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

DEFAULT_BINARY = (
    shutil.which("context-governor")
    or os.path.join(os.path.expanduser("~"), ".cargo", "bin", "context-governor")
)


def run_cg(binary_path: str, args: list[str]) -> str:
    """Run context-governor binary, fail open on missing/error."""
    if not os.path.isfile(binary_path) or not os.access(binary_path, os.X_OK):
        print(f"context-governor binary not found at {binary_path}", file=sys.stderr)
        sys.exit(0)
    try:
        result = subprocess.run(
            [binary_path] + args,
            capture_output=True,
            text=True,
            timeout=60,
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


def cmd_audit_tool_surface(args: argparse.Namespace) -> None:
    tools_json = args.tools_json or json.dumps([])
    output = run_cg(args.binary_path, ["audit-tool-surface", "--tools-json", tools_json])
    print(output)


def cmd_eval_governed_memory(args: argparse.Namespace) -> None:
    cases_json = args.cases_json or json.dumps([])
    output = run_cg(
        args.binary_path,
        [
            "eval-governed-memory",
            "--harness-id",
            args.harness_id or "default",
            "--cases-json",
            cases_json,
        ],
    )
    print(output)


def cmd_eval_rag_leakage(args: argparse.Namespace) -> None:
    cg_args = [
        "eval-rag-leakage",
        "--task-id",
        args.task_id or "default",
        "--closed-book-correct",
        "true" if args.closed_book_correct else "false",
        "--retrieved-correct",
        "true" if args.retrieved_correct else "false",
        "--retrieval-used",
        "true" if args.retrieval_used else "false",
    ]
    output = run_cg(args.binary_path, cg_args)
    print(output)


def cmd_screen_conflicts(args: argparse.Namespace) -> None:
    claims_json = args.claims_json or json.dumps([])
    output = run_cg(args.binary_path, ["screen-conflicts", "--claims-json", claims_json])
    print(output)


def cmd_select_route(args: argparse.Namespace) -> None:
    output = run_cg(args.binary_path, ["select-route", "--query", args.query or ""])
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="context-governor high_roi audit wrapper"
    )
    parser.add_argument(
        "--binary-path",
        default=DEFAULT_BINARY,
        help="path to context-governor binary",
    )
    parser.add_argument(
        "--write-claim-ledger",
        action="store_true",
        help="Write audit result to claim-ledger MCP if available",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("audit-tool-surface")
    p.add_argument("--tools-json", help="JSON array of {name, description}")
    p.set_defaults(func=cmd_audit_tool_surface)

    p = sub.add_parser("eval-governed-memory")
    p.add_argument("--harness-id")
    p.add_argument("--cases-json", help="JSON array of GovernanceCase")
    p.set_defaults(func=cmd_eval_governed_memory)

    p = sub.add_parser("eval-rag-leakage")
    p.add_argument("--task-id")
    p.add_argument(
        "--closed-book-correct", action="store_true", help="Model was correct without retrieval"
    )
    p.add_argument(
        "--retrieved-correct", action="store_true", help="Model was correct with retrieval"
    )
    p.add_argument(
        "--retrieval-used", action="store_true", default=True, help="Retrieval was used"
    )
    p.set_defaults(func=cmd_eval_rag_leakage)

    p = sub.add_parser("screen-conflicts")
    p.add_argument("--claims-json", help="JSON array of {id, text}")
    p.set_defaults(func=cmd_screen_conflicts)

    p = sub.add_parser("select-route")
    p.add_argument("--query", required=True)
    p.set_defaults(func=cmd_select_route)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()