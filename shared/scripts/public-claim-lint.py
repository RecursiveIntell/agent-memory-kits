#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FORBIDDEN = {
    "customers": r"\bcustomers?\b|\bclients?\b",
    "revenue": r"\brevenue\b|\bprofit\b|\bARR\b|\bMRR\b",
    "funding": r"\bfunding\b|\bfunded\b|\binvestors?\b",
    "compliance": r"\bSOC ?2\b|\bHIPAA\b|\bGDPR compliant\b|\bcompliance\b",
    "production_maturity": r"\bproduction[- ]ready\b|\benterprise[- ]ready\b|\bbattle[- ]tested\b",
    "enterprise_adoption": r"\benterprise adoption\b|\bdeployed at\b|\bused by\b",
    "external_superiority": r"\bbest\b|\bfastest\b|\boutperforms\b|\bsuperior to\b|\bbeats\b",
}
EVIDENCE_MARKERS = ["Evidence:", "Receipt:", "Source:", "Verified:", "Benchmark receipt:"]


def has_marker_near(text: str, start: int) -> bool:
    window = text[max(0, start - 240): start + 240]
    return any(marker in window for marker in EVIDENCE_MARKERS)


def scan_file(path: Path) -> list[dict]:
    text = path.read_text(errors="ignore")
    findings = []
    for category, pattern in FORBIDDEN.items():
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if has_marker_near(text, match.start()):
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append({
                "path": str(path),
                "line": line,
                "category": category,
                "match": match.group(0),
                "message": "public/business claim requires nearby evidence marker",
            })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint public docs for unsupported business claims")
    parser.add_argument("paths", nargs="+", help="Files or directories to scan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(f for f in p.rglob("*") if f.suffix.lower() in {".md", ".json", ".toml"})
        elif p.exists():
            files.append(p)

    findings: list[dict] = []
    for f in sorted(set(files)):
        if any(part in {"target", ".git", "__pycache__"} for part in f.parts):
            continue
        findings.extend(scan_file(f))

    result = {"schema": "PublicClaimLintV1", "ok": not findings, "findings": findings}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if findings:
            for item in findings:
                print(f"{item['path']}:{item['line']}: {item['category']}: {item['match']} — {item['message']}")
        else:
            print("public-claim-lint: OK")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
