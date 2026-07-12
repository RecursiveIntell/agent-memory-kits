#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, shutil, subprocess, sys
from pathlib import Path


def resolve_binary() -> str | None:
    env=os.environ.get('CONTEXT_GOVERNOR_BIN')
    if env and os.access(os.path.expanduser(env), os.X_OK): return os.path.expanduser(env)
    for c in (Path.home()/'Coding/Libraries/context-governor/target/release/context-governor', Path.home()/'.local/bin/context-governor', Path.home()/'.cargo/bin/context-governor'):
        if c.exists() and os.access(c, os.X_OK): return str(c)
    return shutil.which('context-governor')

def store_dir() -> Path:
    return Path(os.environ.get('CONTEXT_GOVERNOR_STORE', str(Path.home()/'.local/share/context-governor/receipts'))).expanduser()

def normalize_messages(raw):
    if isinstance(raw, dict):
        raw = raw.get('messages') or raw.get('conversation') or raw.get('transcript') or raw.get('history') or []
    if not isinstance(raw, list): return []
    out=[]
    for i,item in enumerate(raw):
        if not isinstance(item, dict): continue
        content=item.get('content') or item.get('text') or item.get('message') or ''
        if isinstance(content, list): content='\n'.join(map(str, content))
        content=str(content)
        if not content.strip(): continue
        out.append({'id': str(item.get('id') or f'item-{i}'), 'role': str(item.get('role') or item.get('type') or 'user'), 'content': content})
    return out

def run(binary, args, stdin=None, timeout=30):
    proc=subprocess.run([binary,*args], input=json.dumps(stdin) if stdin is not None else None, text=True, capture_output=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f'context-governor exited {proc.returncode}')
    return json.loads(proc.stdout)

def main():
    ap=argparse.ArgumentParser(description='Compact a transcript with context-governor and store receipt.')
    ap.add_argument('--input', help='JSON file containing messages/transcript; stdin if omitted')
    ap.add_argument('--session-id', default='agent-kit-session')
    ap.add_argument('--target-tokens', type=int, default=int(os.environ.get('CONTEXT_GOVERNOR_TARGET_TOKENS','12000')))
    ap.add_argument('--summary-max-chars', type=int, default=int(os.environ.get('CONTEXT_GOVERNOR_SUMMARY_MAX_CHARS','16000')))
    ap.add_argument('--format', choices=['text','json'], default='text')
    args=ap.parse_args()
    binary=resolve_binary()
    if not binary:
        if args.format == 'json':
            print(json.dumps({"ok": False, "error": "context-governor binary not found"}))
        return 0  # fail-open
    try:
        raw = json.loads(Path(args.input).read_text() if args.input else sys.stdin.read())
    except Exception:
        return 0  # fail-open: no stdin or invalid JSON
    messages = normalize_messages(raw)
    if not messages:
        return 0  # fail-open: no transcript available
    req={'session_id': args.session_id, 'messages': messages, 'policy': {'target_tokens': args.target_tokens, 'protect_first_n': 2, 'protect_last_n': 8, 'summary_max_chars': args.summary_max_chars, 'allocator':'deterministic_v1', 'semantic_memory_enabled': False, 'archive_memory_enabled': False, 'budget_mode': os.environ.get('CONTEXT_GOVERNOR_BUDGET_MODE','hard_cascade'), 'token_counter':'approx_chars'}}
    try:
        resp=run(binary, ['compact'], req, timeout=45)
    except SystemExit:
        return 0  # fail-open
    store=store_dir(); store.mkdir(parents=True, exist_ok=True)
    try:
        stored=run(binary, ['store','--dir',str(store)], resp, timeout=20)
    except SystemExit as exc:
        stored = {
            'status': 'failed',
            'exact_recovery_state': 'in_response' if resp.get('exact_store') else 'unavailable',
            'verified': False,
            'error': str(exc),
        }
    receipt=resp.get('receipt') or {}
    if args.format=='json':
        resp['stored_path']=stored.get('path')
        resp['storage']=stored
        print(json.dumps(resp, indent=2))
    else:
        print('Context Governor compacted transcript with receipt-backed exact fallback.')
        print(f"receipt_id: {receipt.get('receipt_id','unknown')}")
        print(f"stored_receipt: {stored.get('path')}")
        print(f"storage_state: {stored.get('exact_recovery_state','unavailable')}")
        print(f"storage_verified: {stored.get('verified',False)}")
        if stored.get('error'):
            print(f"storage_error: {stored['error']}")
        print(f"original_tokens: {receipt.get('original_approx_tokens','unknown')}")
        print(f"compacted_tokens: {receipt.get('compacted_approx_tokens','unknown')}")
        print(f"fallback_refs: {len(receipt.get('exact_fallback_refs') or [])}")
        print('Use context-governor MCP cg_search/cg_expand, or context-governor expand, when exact omitted text matters.')
if __name__=='__main__': main()
