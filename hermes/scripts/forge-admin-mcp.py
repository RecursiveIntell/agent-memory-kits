#!/usr/bin/env python3
"""Hermes wrapper for forge-admin MCP server."""
import importlib.util, os, sys
_shared = os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'scripts')
_spec = importlib.util.spec_from_file_location(
    "forge_admin_mcp", os.path.join(_shared, "forge-admin-mcp.py")
)
if _spec and _spec.loader:
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["forge_admin_mcp"] = _mod
    _spec.loader.exec_module(_mod)
    _mod.main()
else:
    print("forge-admin-mcp.py not found", file=sys.stderr)
    sys.exit(1)