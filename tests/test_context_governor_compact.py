#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "shared/scripts/context-governor-compact.py"
spec = importlib.util.spec_from_file_location("context_governor_compact", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _invoke(run_side_effect):
    transcript = json.dumps({"messages": [{"role": "user", "content": "latest"}]})
    output = io.StringIO()
    with (
        mock.patch.object(module, "resolve_binary", return_value="/tmp/context-governor"),
        mock.patch.object(module, "run", side_effect=run_side_effect),
        mock.patch.object(sys, "argv", [str(SCRIPT), "--format", "json"]),
        mock.patch.object(sys, "stdin", io.StringIO(transcript)),
        redirect_stdout(output),
    ):
        module.main()
    return json.loads(output.getvalue())


def test_json_output_reports_verified_persistence_state():
    response = {
        "receipt": {"receipt_id": "ctxr_test", "exact_fallback_refs": []},
        "compacted_messages": [{"role": "user", "content": "latest"}],
    }
    stored = {
        "receipt_id": "ctxr_test",
        "path": "/tmp/ctxr_test.json",
        "exact_recovery_state": "persisted",
        "verified": True,
    }
    result = _invoke([response, stored])
    assert result["storage"] == stored


def test_json_output_reports_store_failure_instead_of_silent_success():
    response = {
        "receipt": {"receipt_id": "ctxr_test", "exact_fallback_refs": []},
        "compacted_messages": [{"role": "user", "content": "latest"}],
        "exact_store": [{"item_id": "ctxi_test", "content": "omitted exact text"}],
    }
    result = _invoke([response, SystemExit("disk full")])
    assert result["storage"]["status"] == "failed"
    assert result["storage"]["exact_recovery_state"] == "in_response"
    assert result["storage"]["verified"] is False
    assert "disk full" in result["storage"]["error"]
