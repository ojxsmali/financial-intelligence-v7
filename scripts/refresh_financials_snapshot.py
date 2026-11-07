"""Refresh the bundled financial-statement snapshot (offline / SEC-blocked fallback).

Stores the *extracted* annual statements (a few KB per company), not raw XBRL, for a
curated list of widely followed companies. Any other company is fetched live.
The UI always labels snapshot data as such, with its retrieval date.

Usage:  SEC_CONTACT_EMAIL=you@example.com python scripts/refresh_financials_snapshot.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fip.config import BUNDLED_DATA_DIR, sec_contact_email  # noqa: E402
from fip.data_service import load_financials, save_snapshot  # noqa: E402
from fip.universe import read_universe  # noqa: E402

SYMBOLS = [
    # required test set
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "JPM", "XOM", "WMT", "TSLA", "BRK.B",
    # other large, frequently searched registrants across sectors and filer types
    "AVGO", "LLY", "V", "MA", "UNH", "JNJ", "PG", "HD", "COST", "ORCL", "NFLX", "ABBV", "BAC", "KO", "PEP",
    "CVX", "MRK", "ADBE", "CRM", "AMD", "INTC", "CSCO", "DIS", "MCD", "NKE", "IBM", "QCOM", "TXN", "GS",
    "CAT", "BA", "GE", "T", "VZ", "PFE", "TSM", "TM", "ASML", "NVO", "BABA", "SAP", "SHEL", "SONY",
]


def main() -> int:
    if not sec_contact_email():
        print("Set SEC_CONTACT_EMAIL first.", file=sys.stderr)
        return 2
    loaded = read_universe(BUNDLED_DATA_DIR)
    if loaded is None:
        print("data/universe.csv missing; run scripts/refresh_universe.py", file=sys.stderr)
        return 2
    rows = loaded[0].set_index("symbol")
    done, skipped = set(), []
    for symbol in SYMBOLS:
        if symbol not in rows.index or str(rows.loc[symbol, "cik"]) in ("", "<NA>", "nan"):
            skipped.append(f"{symbol} (not listed / no CIK)")
            continue
        cik = int(rows.loc[symbol, "cik"])
        if cik in done:
            continue
        result = load_financials(cik, force_refresh=True)
        if result.ok:
            save_snapshot(result.financials)
            done.add(cik)
            print(f"{symbol}: FY{result.financials.latest.fiscal_year} ({len(result.financials.periods)} years)")
        else:
            skipped.append(f"{symbol} ({result.error_kind}: {result.error[:80]})")
    print(f"\nSaved {len(done)} companies. Skipped: {len(skipped)}")
    for s in skipped:
        print("  -", s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
