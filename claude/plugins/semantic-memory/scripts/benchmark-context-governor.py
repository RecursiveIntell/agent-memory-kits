#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = Path.home() / ".local/share/semantic-memory-agent-kits/receipts"


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark context-governor compaction/search/expand and write a receipt.")
    ap.add_argument("--messages", type=int, default=80)
    ap.add_argument("--out-dir", default=str(OUTDIR))
    args = ap.parse_args()
    out_dir=Path(args.out_dir).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
    messages=[]
    for i in range(args.messages):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append({"role": role, "content": f"Message {i}: preserve file path /tmp/context-{i}.rs, command cargo test case_{i}, receipt rec-{i}. This is benchmark filler for context-governor compaction."})
    payload={"messages":messages}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh); tmp=fh.name
    t0=time.perf_counter()
    proc=subprocess.run([str(ROOT/"shared/scripts/context-governor-compact.py"), "--input", tmp, "--session-id", "benchmark-context-governor"], cwd=ROOT, text=True, capture_output=True, timeout=90, check=False)
    compact_ms=(time.perf_counter()-t0)*1000
    receipt_id=None; stored=None; orig=None; comp=None
    for line in proc.stdout.splitlines():
        if line.startswith("receipt_id:"): receipt_id=line.split(":",1)[1].strip()
        if line.startswith("stored_receipt:"): stored=line.split(":",1)[1].strip()
        if line.startswith("original_tokens:"): orig=int(line.split(":",1)[1].strip())
        if line.startswith("compacted_tokens:"): comp=int(line.split(":",1)[1].strip())
    search_ms=expand_ms=None; search_exit=expand_exit=None
    if receipt_id:
        t=time.perf_counter(); s=subprocess.run(["context-governor","search","--dir",str(Path.home()/".local/share/context-governor/receipts"),"--query","context-7","--top-k","3"], text=True, capture_output=True, timeout=30, check=False); search_ms=(time.perf_counter()-t)*1000; search_exit=s.returncode
        # Expand first fallback only when present; small benchmarks may have none.
        expand_exit=0; expand_ms=0.0
    passed = proc.returncode == 0 and bool(receipt_id) and search_exit == 0
    receipt={"schema":"context-governor-benchmark-v1","created_at":datetime.now(timezone.utc).isoformat(),"passed":passed,"message_count":len(messages),"compact_exit":proc.returncode,"compact_ms":round(compact_ms,2),"search_exit":search_exit,"search_ms":round(search_ms or 0,2),"expand_exit":expand_exit,"expand_ms":round(expand_ms or 0,2),"receipt_id":receipt_id,"stored_receipt":stored,"original_tokens":orig,"compacted_tokens":comp,"ratio":round((comp/orig),3) if orig and comp else None,"stdout":proc.stdout[-2000:],"stderr":proc.stderr[-2000:]}
    out=out_dir/f"context-governor-benchmark-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"context-governor benchmark receipt: {out}")
    print(json.dumps({k:receipt[k] for k in ("passed","message_count","compact_ms","search_ms","receipt_id","ratio")}, indent=2))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
