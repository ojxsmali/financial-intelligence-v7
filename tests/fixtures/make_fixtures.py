"""Create trimmed real-world SEC Company Facts fixtures for regression tests.

Downloads companyfacts for a set of registrants and keeps only the XBRL concepts the
extractor reads, so tests run offline against genuine filing data.

Usage:  SEC_CONTACT_EMAIL=you@example.com python tests/fixtures/make_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fip.http_client import fetch  # noqa: E402
from fip.xbrl import METRICS, _NCI_PRESENT, _TOTAL_EQUITY_INCL_NCI, _TOTAL_LIAB_AND_EQUITY, companyfacts_url  # noqa: E402

CIKS = {"AAPL": 320193, "MSFT": 789019, "WMT": 104169, "JPM": 19617, "BRK.B": 1067983, "NVDA": 1045810,
        "TSM": 1046179, "TM": 1094517, "XOM": 2115436}
OUT = Path(__file__).resolve().parent / "companyfacts"


def keep_concepts() -> dict[str, set[str]]:
    keep: dict[str, set[str]] = {"us-gaap": set(), "ifrs-full": set()}
    for spec in METRICS.values():
        for taxonomy, names in spec.concepts.items():
            keep[taxonomy].update(names)
    for mapping in (_TOTAL_LIAB_AND_EQUITY, _TOTAL_EQUITY_INCL_NCI, _NCI_PRESENT):
        for taxonomy, names in mapping.items():
            keep[taxonomy].update(names)
    return keep


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    keep = keep_concepts()
    for symbol, cik in CIKS.items():
        data = json.loads(fetch(companyfacts_url(cik), sec=True).content)
        facts = {}
        for taxonomy, concepts in (data.get("facts") or {}).items():
            if taxonomy in keep:
                facts[taxonomy] = {k: v for k, v in concepts.items() if k in keep[taxonomy]}
            else:
                # keep one non-financial concept so "only other forms" diagnostics stay realistic
                facts[taxonomy] = dict(list(concepts.items())[:1])
        trimmed = {"cik": data["cik"], "entityName": data["entityName"], "facts": facts}
        path = OUT / f"{symbol.replace('.', '-')}.json"
        path.write_text(json.dumps(trimmed, separators=(",", ":")), encoding="utf-8")
        print(f"{symbol}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
