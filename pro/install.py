#!/usr/bin/env python3
"""install.py — RecursiveIntell Pro plugin installer.

Verifies license, installs pro scripts and MCP servers on top of the free plugin.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

PRO_DIR = Path(__file__).resolve().parent
FREE_DIR = PRO_DIR.parent  # agent-memory-kits root


def main() -> int:
    print("RecursiveIntell Pro Plugin Installer")
    print("=" * 40)

    # Check free plugin is installed
    free_plugin = FREE_DIR / "hermes" / "plugin.json"
    if not free_plugin.exists():
        print(f"ERROR: Free plugin not found at {free_plugin}", file=sys.stderr)
        print("Install the free RecursiveIntell semantic-memory plugin first.", file=sys.stderr)
        return 1

    # Check license key
    license_key = os.environ.get("RI_PRO_LICENSE_KEY")
    if not license_key:
        # Try config file
        config_path = Path.home() / ".ri-pro-config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            license_key = config.get("license_key")

    if not license_key:
        print("ERROR: RI_PRO_LICENSE_KEY not set.", file=sys.stderr)
        print("Contact sales@recursiveintell.com for a license key.", file=sys.stderr)
        print("Set RI_PRO_LICENSE_KEY env var or create ~/.ri-pro-config.json", file=sys.stderr)
        return 1

    print(f"License key: {license_key[:10]}...")

    # Verify license
    sys.path.insert(0, str(PRO_DIR))
    from license_client import get_token, machine_fingerprint

    print(f"Machine fingerprint: {machine_fingerprint()}")
    print("Verifying license...")

    token = get_token()
    if not token:
        print("ERROR: License verification failed.", file=sys.stderr)
        print("Check your license key and server URL.", file=sys.stderr)
        return 1

    print(f"License valid. Features: {token.get('features', [])}")
    print(f"Token expires: {token.get('expires_at', 'unknown')}")

    # Install pro scripts into shared/scripts
    pro_scripts = [
        "release-gate-v2.py",
        "admin-preflight.py",
        "authority-delegation.py",
        "verify-patch.py",
        "benchmark-recall.py",
        "context-governor-audit.py",
        "forge-admin-mcp.py",
        "claim-ledger-mcp.py",
    ]

    shared_scripts = FREE_DIR / "shared" / "scripts"
    for script in pro_scripts:
        src = PRO_DIR / "scripts" / script
        if not src.exists():
            # Fall back to shared/scripts if already there
            src = shared_scripts / script
        if src.exists():
            dst = shared_scripts / script
            if src != dst:
                shutil.copy2(src, dst)
                dst.chmod(0o755)
                print(f"  installed: {script}")

    # Install license client into shared/scripts
    license_client_src = PRO_DIR / "license_client.py"
    license_client_dst = shared_scripts / "license_client.py"
    shutil.copy2(license_client_src, license_client_dst)
    print("  installed: license_client.py")

    # Write config file
    config = {
        "license_key": license_key,
        "server": os.environ.get("RI_PRO_LICENSE_SERVER", "https://license.recursiveintell.com"),
    }
    config_path = Path.home() / ".ri-pro-config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    config_path.chmod(0o600)
    print(f"  config: {config_path}")

    print()
    print("Pro plugin installed successfully.")
    print("Restart your agent to activate the Pro MCP servers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())