"""Rebuild the bundled listing snapshot data/universe.csv from the official directories.

The running app refreshes its own copy every 24 h; this bundled snapshot is the
offline / blocked-network fallback and is refreshed daily by GitHub Actions.

Usage:  SEC_CONTACT_EMAIL=you@example.com python scripts/refresh_universe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fip.config import BUNDLED_DATA_DIR, sec_contact_email  # noqa: E402
from fip.universe import download_and_build, save_universe  # noqa: E402


def main() -> int:
    if not sec_contact_email():
        print("Set SEC_CONTACT_EMAIL first.", file=sys.stderr)
        return 2
    frame, meta = download_and_build()
    save_universe(frame, meta, BUNDLED_DATA_DIR)
    print(f"{meta['total_securities']} securities, {meta['companies']} companies, {meta['with_cik']} with SEC CIK")
    print("by exchange:", meta["by_exchange"])
    print("by type:", meta["by_type"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
