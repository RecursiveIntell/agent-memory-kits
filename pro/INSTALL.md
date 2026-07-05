# RecursiveIntell Pro install

Pro is a separate business/admin plugin layered on top of the free memory plugin.

## Requirements

- Free `semantic-memory` plugin installed first.
- License server URL.
- Yearly license key.
- Local config file at `~/.ri-pro-config.json` with mode `0600`.

Example config:

```json
{
  "server_url": "https://license.example.com",
  "license_key": "ri-pro-..."
}
```

## Install

```bash
python3 pro/install.py \
  --server-url https://license.example.com \
  --license-key ri-pro-...
```

## Verify

```bash
python3 pro/scripts/pro-doctor.py
```

The doctor emits `RIProDoctorReceiptV1`. A passing doctor means:

- config exists and is private;
- license server is reachable;
- license token is trusted;
- Pro MCP wrapper files exist.

## Failure behavior

If `RI_PRO_ENFORCE=1`, Pro scripts block when the license is missing, expired, revoked, or untrusted. Development skip mode (`RI_PRO_LICENSE_SKIP=1`) is explicitly marked untrusted/skipped in receipts and must not be accepted as business proof.
