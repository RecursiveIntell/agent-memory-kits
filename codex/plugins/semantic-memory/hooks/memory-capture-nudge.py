#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from common import debug


def main() -> int:
    debug("Stop semantic-memory capture nudge")
    print(
        "Semantic memory reminder: before ending substantial work or losing context, persist durable, "
        "verified facts with sm_add_fact after sm_search/sm_list_facts dedupe. Store decisions, stable "
        "project/config facts, and corrections; do not store secrets, guesses, raw logs, or ephemeral conversation.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
