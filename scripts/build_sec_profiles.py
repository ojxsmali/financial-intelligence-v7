"""Build data/sec_profiles.csv: SIC industry, country and fiscal-year end per registrant.

Reads https://data.sec.gov/submissions/CIK##########.json once per exchange-listed
company (≈6–7k requests at 5 req/s ≈ 25 minutes). The script is resumable and
incremental: rows already present are kept unless --refresh is passed, so the
scheduled GitHub Action only fetches newly listed registrants.

Usage:  SEC_CONTACT_EMAIL=you@example.com python scripts/build_sec_profiles.py [--refresh] [--limit N]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fip.config import BUNDLED_DATA_DIR, sec_contact_email  # noqa: E402
from fip.http_client import DataSourceError, NotFoundError, fetch  # noqa: E402
from fip.universe import UNIVERSE_FILE, read_universe  # noqa: E402

SCHEMA_VERSION = "2"   # v2: country derived from EDGAR state/country codes
FIELDS = ["cik", "sec_name", "sic", "sic_description", "owner_org", "country", "state_of_incorporation",
          "fiscal_year_end", "entity_type", "filer_category", "schema_version"]


# EDGAR "stateOrCountry" codes for US states, DC and territories. Every other code
# (e.g. M0 = Japan, F4 = China, X0 = United Kingdom) denotes a foreign location.
US_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "PR", "VI", "GU",
    "AS", "MP",
}


def country_from_address(address: dict) -> str:
    code = (address.get("stateOrCountry") or "").strip().upper()
    if code in US_CODES and not address.get("isForeignLocation"):
        return "United States"
    if code or address.get("isForeignLocation") or address.get("country"):
        name = address.get("country") or address.get("stateOrCountryDescription") or "Non-US"
        return str(name).title() if str(name).isupper() else str(name)
    return ""


def profile_from_submissions(data: dict) -> dict:
    addresses = data.get("addresses") or {}
    country = country_from_address(addresses.get("business") or {}) or country_from_address(addresses.get("mailing") or {})
    return {
        "cik": int(data["cik"]),
        "sec_name": data.get("name") or "",
        "sic": data.get("sic") or "",
        "sic_description": data.get("sicDescription") or "",
        "owner_org": data.get("ownerOrg") or "",
        "country": country,
        "state_of_incorporation": data.get("stateOfIncorporation") or "",
        "fiscal_year_end": data.get("fiscalYearEnd") or "",
        "entity_type": data.get("entityType") or "",
        "filer_category": data.get("category") or "",
        "schema_version": SCHEMA_VERSION,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-fetch every registrant")
    parser.add_argument("--limit", type=int, default=0, help="stop after N new requests (testing)")
    args = parser.parse_args()

    if not sec_contact_email():
        print("Set SEC_CONTACT_EMAIL first.", file=sys.stderr)
        return 2
    loaded = read_universe(BUNDLED_DATA_DIR)
    if loaded is None:
        print(f"Run scripts/refresh_universe.py first ({UNIVERSE_FILE} missing).", file=sys.stderr)
        return 2
    universe, _ = loaded
    ciks = sorted({int(c) for c in universe.loc[universe["is_company"], "cik"].dropna()})

    out_path = BUNDLED_DATA_DIR / "sec_profiles.csv"
    existing: dict[int, dict] = {}
    if out_path.exists() and not args.refresh:
        with out_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("schema_version") == SCHEMA_VERSION:   # older rows are re-fetched
                    existing[int(row["cik"])] = row
    todo = [c for c in ciks if c not in existing]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(ciks)} registrants, {len(existing)} cached, {len(todo)} to fetch", flush=True)

    def one(cik: int):
        try:
            result = fetch(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", sec=True)
            return cik, profile_from_submissions(json.loads(result.content)), ""
        except NotFoundError:
            return cik, None, "not found"
        except (DataSourceError, ValueError) as exc:
            return cik, None, getattr(exc, "user_message", str(exc))

    # A few workers hide network latency; the shared SEC limiter still caps throughput at 5 req/s.
    failures = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, (cik, profile, error) in enumerate(pool.map(one, todo), 1):
            if profile is not None:
                existing[cik] = profile
            else:
                failures += 1
                if error != "not found":
                    print(f"  CIK {cik}: {error}", flush=True)
            if i % 250 == 0:
                _write(out_path, existing)
                print(f"  {i}/{len(todo)} fetched ({failures} failures)", flush=True)

    keep = {c: r for c, r in existing.items() if c in set(ciks)}
    _write(out_path, keep)
    print(f"Wrote {len(keep)} profiles to {out_path} ({failures} failures)")
    return 0


def _write(path: Path, rows: dict[int, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for cik in sorted(rows):
            writer.writerow(rows[cik])
    tmp.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
