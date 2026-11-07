"""Fetch → validate → cache pipeline for company financials and profiles.

Order of preference for financial statements of one registrant:

1. Fresh disk cache (< 12 h)          -> origin "disk cache"
2. Live SEC Company Facts request      -> origin "live"
3. Older disk cache (any age)          -> origin "disk cache (stale)" + visible warning
4. Bundled snapshot in data/           -> origin "bundled snapshot" + visible warning
5. Typed error with an explanation      (nothing is ever substituted from another company)

This module is Streamlit-free; the UI layer adds in-memory caching on top.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fip.config import BUNDLED_DATA_DIR, cache_dir
from fip.filings import CompanyProfile, parse_submissions, submissions_url
from fip.http_client import ConfigurationError, DataSourceError, NotFoundError, fetch
from fip.xbrl import CompanyFinancials, NoAnnualDataError, companyfacts_url, extract_financials

FINANCIALS_TTL = 12 * 3600
PROFILE_TTL = 24 * 3600
SNAPSHOT_DIR = BUNDLED_DATA_DIR / "financials_snapshot"


@dataclass
class FinancialsResult:
    cik: int
    financials: CompanyFinancials | None = None
    origin: str = ""
    error: str = ""            # user-facing explanation when financials is None
    error_kind: str = ""       # no_annual_data | not_found | config | upstream
    notices: list = field(default_factory=list)   # visible caveats (stale data, fallbacks)

    @property
    def ok(self) -> bool:
        return self.financials is not None


def _disk_path(kind: str, cik: int) -> Path:
    directory = cache_dir() / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"CIK{int(cik):010d}.json"


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def _read_cached(path: Path):
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload, time.time() - path.stat().st_mtime
    except (OSError, ValueError):
        return None, None


def _age_text(seconds: float) -> str:
    hours = seconds / 3600
    return f"{hours:.0f} hours" if hours < 48 else f"{hours / 24:.0f} days"


def load_financials(cik: int, *, force_refresh: bool = False, contact_email: str | None = None,
                    fetcher=fetch) -> FinancialsResult:
    cik = int(cik)
    result = FinancialsResult(cik=cik)
    path = _disk_path("financials", cik)
    cached, age = _read_cached(path)

    if cached is not None and not force_refresh and age is not None and age < FINANCIALS_TTL:
        if "no_annual_data" in cached:
            result.error, result.error_kind, result.origin = cached["no_annual_data"], "no_annual_data", "disk cache"
            return result
        result.financials = CompanyFinancials.from_dict(cached)
        result.financials.origin = "disk cache"
        result.origin = "disk cache"
        return result

    live_error = None
    try:
        raw = fetcher(companyfacts_url(cik), sec=True, contact_email=contact_email)
        facts = json.loads(raw.content)
        try:
            fin = extract_financials(facts)
        except NoAnnualDataError as exc:
            _write_json(path, {"no_annual_data": exc.user_message})
            result.error, result.error_kind, result.origin = exc.user_message, "no_annual_data", "live"
            return result
        fin.origin = "live"
        _write_json(path, fin.to_dict())
        result.financials, result.origin = fin, "live"
        return result
    except NotFoundError:
        result.error = ("SEC has no XBRL Company Facts for this registrant (HTTP 404). This is typical for funds, "
                        "trusts, recently listed companies and filers that do not submit structured financial data.")
        result.error_kind = "not_found"
        return result
    except ConfigurationError as exc:
        live_error = exc
        result.error_kind = "config"
    except DataSourceError as exc:
        live_error = exc
        result.error_kind = "upstream"
    except ValueError:
        live_error = DataSourceError("SEC returned data that could not be parsed.")
        result.error_kind = "upstream"

    reason = live_error.user_message if isinstance(live_error, DataSourceError) else str(live_error)
    if cached is not None and "no_annual_data" not in cached:
        result.financials = CompanyFinancials.from_dict(cached)
        result.financials.origin = "disk cache (stale)"
        result.origin = "disk cache (stale)"
        result.notices.append(f"Live SEC refresh failed — {reason} Showing figures cached {_age_text(age)} ago.")
        return result

    snapshot = SNAPSHOT_DIR / f"CIK{cik:010d}.json"
    if snapshot.exists():
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        result.financials = CompanyFinancials.from_dict(data)
        result.financials.origin = "bundled snapshot"
        result.origin = "bundled snapshot"
        result.notices.append(
            f"Live SEC request failed — {reason} Showing the bundled snapshot retrieved "
            f"{data.get('retrieved_at', 'at an unknown time')[:10]}; newer filings may exist."
        )
        return result

    result.error = reason
    return result


def load_profile(cik: int, *, contact_email: str | None = None, fetcher=fetch) -> tuple[CompanyProfile | None, str]:
    """Return (profile, error_message). Profiles are optional enrichment; failures are non-fatal."""
    cik = int(cik)
    path = _disk_path("profiles", cik)
    cached, age = _read_cached(path)
    if cached is not None and age is not None and age < PROFILE_TTL:
        return CompanyProfile(**cached), ""
    try:
        raw = fetcher(submissions_url(cik), sec=True, contact_email=contact_email)
        profile = parse_submissions(json.loads(raw.content))
        _write_json(path, profile.to_dict())
        return profile, ""
    except (DataSourceError, ValueError) as exc:
        message = getattr(exc, "user_message", str(exc))
        if cached is not None:
            return CompanyProfile(**cached), f"Profile refresh failed ({message}); showing cached profile."
        return None, message


def newer_annual_filing_note(fin: CompanyFinancials, profile: CompanyProfile | None) -> str:
    """Detect annual reports that were filed but whose statements are absent from XBRL Company Facts."""
    if profile is None or not profile.annual_filings:
        return ""
    latest_end = fin.latest.end
    newer = [f for f in profile.annual_filings
             if f["form"] in ("10-K", "20-F", "40-F") and f["report_date"] and f["report_date"] > latest_end]
    if not newer:
        return ""
    f = newer[0]
    return (f"A newer {f['form']} for the period ending {f['report_date']} was filed on {f['filing_date']}, but its "
            "financial statements are not yet in SEC's structured Company Facts data. Figures below stop at "
            f"{latest_end}; read the newer filing directly via the Sources page.")


def save_snapshot(fin: CompanyFinancials) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"CIK{fin.cik:010d}.json"
    payload = fin.to_dict()
    payload["origin"] = "bundled snapshot"
    _write_json(path, payload)
    return path


def utc_now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
