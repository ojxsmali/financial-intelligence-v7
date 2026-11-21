"""JSON API over the ``fip`` core, for the React web app.

Runs locally with ``uvicorn fip.api:app`` and on Vercel as a Python function
(``api/index.py``). Everything here is a thin adapter: data rules live in the core
modules and are shared with the Streamlit desktop app.

Security
* The Gemini key never leaves the server; responses only say whether it is configured.
* Errors return safe, fixed messages; stack traces are logged, never sent.
* An optional visitor-supplied SEC contact e-mail (header ``X-SEC-Contact``) is used only
  as the SEC User-Agent when the server has none configured, and is never logged or stored.
"""
from __future__ import annotations

import logging
import re
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

if os.environ.get("VERCEL"):                               # read-only bundle: caches go to /tmp
    os.environ.setdefault("FIP_CACHE_DIR", "/tmp/fip-cache")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi import FastAPI, Query, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from fip import APP_NAME, VERSION, config  # noqa: E402
from fip.ai_guard import AiGuard  # noqa: E402
from fip.data_service import load_events, load_financials, load_profile, newer_annual_filing_note  # noqa: E402
from fip.events import latest_annual_filing_date  # noqa: E402
from fip.health import health_score  # noqa: E402
from fip.observability import Timer, log_event, new_ref, report, reset_ref, set_ref  # noqa: E402
from fip import screener as screener_mod  # noqa: E402
from fip.exports import (MAX_UPLOAD_BYTES, CsvImportError, long_format, read_user_csv, to_csv_bytes,  # noqa: E402
                         user_csv_to_financials)
from fip.filings import FORM_DESCRIPTIONS, CompanyProfile  # noqa: E402
from fip.formatting import CURRENCY_SYMBOLS  # noqa: E402
from fip.http_client import DataSourceError  # noqa: E402
from fip.gemini import (DEFAULT_CHAIN, FREE_TIER_MODELS, MAX_COMPANIES, MAX_QUESTION_CHARS,  # noqa: E402
                        GeminiError, build_fact_pack, generate, resolve_models)
from fip.insights import generate_insights  # noqa: E402
from fip.metrics import RATIO_DEFINITIONS, annual_table, comparison_frame, comparison_warnings, revenue_cagr  # noqa: E402
from fip.sectors import SECTORS  # noqa: E402
from fip.universe import (COMPANY_TYPES, INSTRUMENT_TYPES, NASDAQ_LISTED_URL, OTHER_LISTED_URL,  # noqa: E402
                          SEC_TICKERS_URL, add_search_columns, load_universe, search, share_classes, symbol_key)
from fip.xbrl import METRICS, filing_index_url  # noqa: E402

log = logging.getLogger("fip.api")
ON_VERCEL = bool(os.environ.get("VERCEL"))
MAX_COMPARE = 6
DEFAULT_COMPARE = ["AAPL", "MSFT", "GOOGL", "NVDA"]
RATIO_KEYS = ["revenue_growth", "net_income_growth", "gross_margin", "operating_margin", "net_margin", "fcf_margin",
              "cash_conversion", "liabilities_to_assets", "return_on_equity", "net_margin_change",
              "operating_margin_change"]
PRESETS = {
    "Performance": "Explain how revenue and profitability changed over the last fiscal years. Which changes are "
                   "largest, and what would need to be checked in the filings to explain them?",
    "Compare": "Compare these companies' revenue growth, operating margin and net margin. Note fiscal-year and "
               "currency differences that limit the comparison.",
    "Operating vs reported": "Compare operating income with reported net income. Where do they diverge, and what "
                             "non-operating items might explain the gap?",
    "Cash quality": "Assess how well net income is backed by operating cash flow and free cash flow.",
}
CACHE_PUBLIC = "public, max-age=60, s-maxage=1800, stale-while-revalidate=3600"

app = FastAPI(title=f"{APP_NAME} API", version=VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None)


# ---------------------------------------------------------------- helpers
def clean(value):
    """JSON-safe: NaN/inf → None, numpy scalars → Python, recursively."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NaT:
        return None
    return value


def ok(payload, *, cache: str | None = CACHE_PUBLIC, status: int = 200) -> JSONResponse:
    headers = {"Cache-Control": cache or "no-store"}
    return JSONResponse(clean(payload), status_code=status, headers=headers)


# Visitor-facing wording. Internal details (status codes, exception text, env var names) go to the
# private log only; visitors get one of these, plus a reference ID they can quote.
MSG_INTERNAL = "Something went wrong. Please try again shortly."
MSG_DATA_UNAVAILABLE = "Financial data is temporarily unavailable. Please try again later."
MSG_SERVICE_UNAVAILABLE = "This service is temporarily unavailable. We are working to restore it."
MSG_ASSISTANT_DOWN = "The research assistant is temporarily unavailable. Please try again shortly."
MSG_ASSISTANT_OFF = "The research assistant isn't available on this site right now. Every other page works as usual."
MSG_ASSISTANT_QUOTA = "The research assistant has reached its usage limit for now. Please try again later."
SAFE_COMPANY_MESSAGES = {
    "no_annual_data": "No audited annual financial statements are available for this company yet. Its filings so far "
                      "don't include an annual report with structured financial data.",
    "not_found": "This company doesn't publish structured annual financial data with the SEC. That's common for "
                 "funds, trusts and very new listings.",
    "config": MSG_DATA_UNAVAILABLE,
    "upstream": MSG_DATA_UNAVAILABLE,
}


def fail(status: int, kind: str, message: str) -> JSONResponse:
    ref = current_ref_or_new()
    return JSONResponse({"error": {"kind": kind, "message": message, "ref": ref}}, status_code=status,
                        headers={"Cache-Control": "no-store", "X-Request-ID": ref})


def current_ref_or_new() -> str:
    from fip.observability import _ref
    return _ref.get() or new_ref()


def safe_notices(result) -> list[str]:
    """Rewrite data-source caveats in plain language (no status codes or service internals)."""
    out = []
    for n in result.notices:
        if result.origin == "disk cache (stale)":
            age = re.search(r"cached (.+?) ago", n)
            out.append("Live data couldn't be refreshed just now, so these figures come from a saved copy"
                       + (f" from {age.group(1)} ago." if age else "."))
        elif result.origin == "bundled snapshot":
            when = re.search(r"retrieved (\d{4}-\d{2}-\d{2})", n)
            out.append("Live data couldn't be refreshed just now, so these figures come from a saved snapshot"
                       + (f" taken {when.group(1)}" if when else "") + "; newer filings may exist.")
        else:
            out.append("Some figures could not be refreshed just now and may be slightly out of date.")
    return out


@app.exception_handler(RequestValidationError)
async def _invalid(request: Request, exc: RequestValidationError):
    fields = ", ".join(str(e.get("loc", ["", "?"])[-1]) for e in exc.errors()[:3])
    log_event("info", "invalid_request", path=request.url.path, fields=fields)
    return fail(422, "bad_request", "Some of the information sent was not valid. Check it and try again.")


@app.exception_handler(StarletteHTTPException)
async def _http(request: Request, exc: StarletteHTTPException):
    message = "This API route does not exist." if exc.status_code == 404 else "The request could not be handled."
    return fail(exc.status_code, "not_found" if exc.status_code == 404 else "http", message)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    report("internal", "backend", f"Unhandled exception on {request.method} {request.url.path}", exc=exc,
           severity="critical", temporary=False, threshold=1, fingerprint=f"internal:{type(exc).__name__}:{request.url.path}",
           path=request.url.path)
    return fail(500, "internal", MSG_INTERNAL)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    ref = new_ref()
    token = set_ref(ref)
    timer = Timer()
    try:
        try:
            response = await call_next(request)
        except Exception as exc:          # anything that escaped the route and its handlers
            report("internal", "backend", f"Unhandled exception on {request.method} {request.url.path}", exc=exc,
                   severity="critical", temporary=False, threshold=1,
                   fingerprint=f"internal:{type(exc).__name__}:{request.url.path}", path=request.url.path)
            response = fail(500, "internal", MSG_INTERNAL)
        status = response.status_code
        if status >= 500 or timer.ms > 20_000:
            log_event("error" if status >= 500 else "warning", "request", method=request.method,
                      path=request.url.path, status=status, duration_ms=timer.ms)
        elif status >= 400:
            log_event("info", "request", method=request.method, path=request.url.path, status=status,
                      duration_ms=timer.ms)
    finally:
        reset_ref(token)
    response.headers["X-Request-ID"] = ref
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def contact_email(request: Request | None) -> str:
    configured = config.sec_contact_email()
    if configured or request is None:
        return configured
    supplied = (request.headers.get("x-sec-contact") or "").strip()
    return supplied if config.is_valid_email(supplied) else ""


# ---------------------------------------------------------------- universe (process cache)
@dataclass
class Universe:
    frame: pd.DataFrame
    by_symbol: dict
    meta: dict
    origin: str
    warning: str
    loaded_at: float


_UNIVERSE: Universe | None = None
_UNIVERSE_LOCK = threading.Lock()
UNIVERSE_TTL = 6 * 3600


def get_universe() -> Universe:
    global _UNIVERSE
    with _UNIVERSE_LOCK:
        if _UNIVERSE is None or time.time() - _UNIVERSE.loaded_at > UNIVERSE_TTL:
            # On Vercel a cold start must stay fast: use the bundled listing snapshot (refreshed in the repo).
            state = load_universe(allow_refresh=not ON_VERCEL, contact_email=config.sec_contact_email() or None)
            frame = add_search_columns(state.frame)
            records = frame.drop(columns=["_sym", "_key", "_name"]).to_dict("records")
            _UNIVERSE = Universe(frame, {r["symbol"]: r for r in records}, state.meta, state.origin, state.warning,
                                 time.time())
        return _UNIVERSE


def resolve_symbol(raw: str) -> str:
    """Exact symbol, else the listing whose normalised key matches (BRK-B, brk/b, BRKB -> BRK.B)."""
    u = get_universe()
    sym = (raw or "").upper().strip()[:12]
    if sym in u.by_symbol:
        return sym
    key = symbol_key(sym)
    if key:
        hit = u.frame[u.frame["_key"] == key]
        if not hit.empty:
            return str(hit.sort_values("is_company", ascending=False).iloc[0]["symbol"])
    return sym


def _fye_label(value) -> str:
    text = "" if value is None or (isinstance(value, float) and math.isnan(value)) else str(value)
    text = text.split(".")[0]
    return CompanyProfile(cik=0, name="", fiscal_year_end=text.zfill(4) if text.isdigit() else "").fiscal_year_end_label


def entry_json(row: dict) -> dict:
    cik = row.get("cik")
    has_cik = cik is not None and not (isinstance(cik, float) and math.isnan(cik))
    return {
        "symbol": row["symbol"], "name": row.get("name") or row.get("sec_name") or row["symbol"],
        "exchange": row.get("exchange"), "instrument_type": row.get("instrument_type"),
        "is_company": bool(row.get("is_company")), "cik": int(cik) if has_cik else None,
        "sector": row.get("sector"), "sic_description": row.get("sic_description"), "country": row.get("country"),
        "fiscal_year_end": _fye_label(row.get("fiscal_year_end")), "financial_status": row.get("financial_status"),
    }


# ---------------------------------------------------------------- serializers
def financials_json(fin) -> dict:
    df = annual_table(fin)
    periods = {p.end: p for p in fin.periods}
    years = []
    for _, row in df.iterrows():
        p = periods[row["period_end"]]
        facts = {}
        for key, fact in p.values.items():
            facts[key] = {"concept": fact.formula or f"{fin.taxonomy}:{fact.concept}", "derived": fact.derived,
                          "formula": fact.formula, "restated": fact.restated,
                          "original_value": fact.original_value if fact.restated else None, "form": fact.form, "filed": fact.filed,
                          "accession": fact.accession}
        years.append({
            "fiscal_year": int(row["fiscal_year"]), "period_start": row["period_start"], "period_end": row["period_end"],
            "form": row["form"], "filed": row["filed"], "accession": row["accession"],
            "filing_index_url": filing_index_url(fin.cik, row["accession"]) if row["accession"] else "",
            "consecutive": bool(row.get("consecutive", False)),
            "values": {k: row.get(k) for k in METRICS},
            "ratios": {k: row.get(k) for k in RATIO_KEYS},
            "facts": facts,
        })
    cagr_value, cagr_years = revenue_cagr(df)
    return {
        "cik": fin.cik, "entity_name": fin.entity_name, "taxonomy": fin.taxonomy,
        "basis": "IFRS" if fin.taxonomy == "ifrs-full" else "US GAAP", "currency": fin.currency,
        "origin": fin.origin, "retrieved_at": fin.retrieved_at, "source_url": getattr(fin, "source_url", ""),
        "warnings": list(fin.warnings), "excluded_note": fin.excluded_note, "years": years,
        "revenue_cagr": {"value": cagr_value, "years": cagr_years},
        "insights": [i.__dict__ for i in generate_insights(df, fin.currency, fin.warnings)],
    }


def profile_json(profile: CompanyProfile | None) -> dict | None:
    if profile is None:
        return None
    return {"name": profile.name, "sic_description": profile.sic_description, "sector": profile.sector,
            "fiscal_year_end": profile.fiscal_year_end_label, "location": profile.location,
            "edgar_url": profile.edgar_url, "annual_filings": profile.annual_filings[:12]}


ERROR_TITLES = {"no_annual_data": "Annual financial statements unavailable",
                "not_found": "No structured SEC financial data",
                "config": "SEC contact e-mail required",
                "upstream": "SEC data temporarily unavailable"}


def company_payload(symbol: str, request: Request | None, *, refresh: bool = False) -> dict:
    universe = get_universe()
    symbol = resolve_symbol(symbol)
    row = universe.by_symbol.get(symbol)
    if row is None:
        return {"symbol": symbol, "status": "not_listed", "error": {
            "kind": "not_listed", "title": "Symbol not found in current listings",
            "message": f"{symbol} is not in today's exchange directories. It may have been delisted or renamed. "
                       "Search for the company in Explorer."}}
    entry = entry_json(row)
    base = {"symbol": symbol, "entry": entry}
    if entry["instrument_type"] not in COMPANY_TYPES or entry["cik"] is None:
        if entry["instrument_type"] in COMPANY_TYPES:
            message = ("This listing has no matching SEC registrant in SEC's ticker-to-CIK file (common for banks that "
                       "file with banking regulators instead of the SEC, and for brand-new listings). No financial "
                       "statements are shown rather than borrowing another entity's data.")
        else:
            message = (f"{entry['instrument_type']} securities are not operating companies and do not publish 10-K "
                       "financial statements. Choose a common stock or ADR to see company fundamentals.")
        return {**base, "status": "not_company", "error": {
            "kind": "not_company", "title": "No SEC financial statements for this security", "message": message}}

    contact = contact_email(request) or None
    events, events_at, events_error = load_events(entry["cik"], contact_email=contact, limit=12)
    result = load_financials(entry["cik"], force_refresh=refresh, contact_email=contact)
    # Auto-update: an annual report on EDGAR that is newer than our copy of the data triggers a refresh.
    latest_annual = latest_annual_filing_date(events)
    if (result.ok and not refresh and latest_annual and result.financials.retrieved_at
            and latest_annual > result.financials.retrieved_at[:10] and latest_annual > result.financials.latest.filed):
        result = load_financials(entry["cik"], force_refresh=True, contact_email=contact)
    profile, profile_error = load_profile(entry["cik"], contact_email=contact)
    if events_error:
        report("sec_outage", "sec", "SEC filings feed could not be loaded", severity="warning", threshold=5,
               fingerprint="sec_outage:events", detail=events_error)
    payload = {**base, "profile": profile_json(profile), "profile_error": "",
               "events": [e.to_dict() for e in events], "events_checked_at": events_at,
               "events_error": "The filing feed is unavailable right now." if events_error and not events else "",
               "share_classes": [s for s in share_classes(universe.frame, entry["cik"]) if s != symbol]}
    if profile is not None:
        entry["sector"] = profile.sector or entry["sector"]
        entry["sic_description"] = profile.sic_description or entry["sic_description"]
        entry["fiscal_year_end"] = profile.fiscal_year_end_label
    if result.notices:
        report("sec_outage", "sec", "Live SEC refresh failed; served cached or bundled data", severity="warning",
               threshold=3, fingerprint="sec_outage:financials", symbol=symbol, origin=result.origin,
               detail=result.notices[0])
    if not result.ok:
        kind = result.error_kind or "upstream"
        if kind == "config":
            report("config", "config", "SEC contact e-mail is not configured on the server", severity="critical",
                   temporary=False, threshold=1, fingerprint="config:sec_contact")
        elif kind == "upstream":
            report("sec_outage", "sec", "SEC financial data could not be loaded and no saved copy exists",
                   severity="error", threshold=3, fingerprint="sec_outage:financials", symbol=symbol,
                   detail=result.error)
        return {**payload, "status": "error", "error": {
            "kind": kind, "retryable": kind in ("upstream", "config"),
            "title": ERROR_TITLES.get(kind, "Financial data unavailable") if kind not in ("config", "upstream")
            else "Financial data temporarily unavailable",
            "message": SAFE_COMPANY_MESSAGES.get(kind, MSG_DATA_UNAVAILABLE),
            "edgar_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={entry['cik']:010d}"}}
    fin = result.financials
    return {**payload, "status": "ok", "financials": financials_json(fin), "notices": safe_notices(result),
            "health": health_score(annual_table(fin)).to_dict(),
            "newer_filing_note": newer_annual_filing_note(fin, profile)}


# ---------------------------------------------------------------- routes: data
@app.get("/api/health")
def health():
    return ok({"ok": True, "version": VERSION}, cache=None)


@app.get("/api/meta")
def meta():
    u = get_universe()
    models, rejected = resolve_models(config.get_setting("GEMINI_MODELS"))
    return ok({
        "app": APP_NAME, "version": VERSION,
        "universe": {"total": int(u.meta.get("total_securities", len(u.frame))),
                     "companies": int(u.meta.get("companies", 0)), "with_cik": int(u.meta.get("with_cik", 0)),
                     "origin": u.origin, "built_at": str(u.meta.get("built_at", "")), "warning": u.warning,
                     "nasdaq_file_created": u.meta.get("nasdaq_file_created", ""),
                     "other_file_created": u.meta.get("other_file_created", ""),
                     "exchanges": sorted(u.frame["exchange"].dropna().unique().tolist()),
                     "by_exchange": u.frame["exchange"].value_counts().to_dict(),
                     "by_type": u.frame["instrument_type"].value_counts().to_dict()},
        "instrument_types": INSTRUMENT_TYPES, "company_types": list(COMPANY_TYPES), "sectors": list(SECTORS),
        "gemini_configured": config.gemini_configured(), "sec_contact_configured": bool(config.sec_contact_email()),
        "default_compare": DEFAULT_COMPARE, "max_compare": MAX_COMPARE, "currencies": list(CURRENCY_SYMBOLS),
        "models": models,
    }, cache="public, max-age=60, s-maxage=600")


@app.get("/api/symbols")
def symbols(q: str = Query("", max_length=80), limit: int = Query(12, ge=1, le=30)):
    u = get_universe()
    if not q.strip():
        return ok({"results": []})
    found = search(u.frame, q, types=list(COMPANY_TYPES), only_with_filings=True).head(limit)
    return ok({"results": [{"symbol": r["symbol"], "name": r["name"], "exchange": r["exchange"]}
                           for r in found.to_dict("records")]})


@app.get("/api/search")
def search_route(q: str = Query("", max_length=80), exchange: list[str] = Query(default=[]),
                 type: list[str] = Query(default=[]), sector: list[str] = Query(default=[]),  # noqa: A002
                 filers: bool = True, page: int = Query(1, ge=1), page_size: int = Query(25, ge=5, le=100)):
    u = get_universe()
    results = search(u.frame, q, exchanges=exchange, types=type, sectors=sector, only_with_filings=filers)
    if not q.strip():
        results = results.sort_values(["is_company", "symbol"], ascending=[False, True])
    total = len(results)
    pages = max(1, math.ceil(total / page_size))
    page = min(page, pages)
    view = results.iloc[(page - 1) * page_size: page * page_size]
    return ok({"total": total, "page": page, "pages": pages, "page_size": page_size,
               "by_exchange": results["exchange"].value_counts().head(6).to_dict(),
               "rows": [entry_json(r) for r in view.to_dict("records")]})


@app.get("/api/company/{symbol}")
def company(symbol: str, request: Request, refresh: bool = False):
    payload = company_payload(symbol, request, refresh=refresh)
    status = 404 if payload["status"] == "not_listed" else 200
    return ok(payload, cache="no-store" if refresh or request.headers.get("x-sec-contact") else CACHE_PUBLIC,
              status=status)


def _parse_symbols(raw: str, limit: int = MAX_COMPARE) -> list[str]:
    out = []
    for s in (raw or "").split(","):
        s = resolve_symbol(s) if s.strip() else ""
        if s and s not in out:
            out.append(s)
    return out[:limit]


def _load_many(symbols: list[str], request: Request | None):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda s: company_payload(s, request), symbols))


@app.get("/api/compare")
def compare(request: Request, symbols: str = Query("", max_length=120)):
    wanted = _parse_symbols(symbols)
    payloads = _load_many(wanted, request)
    u = get_universe()
    items, companies = [], []
    for p in payloads:
        name = (p.get("entry") or {}).get("name") or p["symbol"]
        if p["status"] == "ok":
            companies.append({"symbol": p["symbol"], "name": name, "ok": True, "notices": p.get("notices", [])})
        else:
            companies.append({"symbol": p["symbol"], "name": name, "ok": False,
                              "error": p.get("error", {}).get("message", "No data.")})
    # Re-load the financial objects for the core comparison helpers (disk-cached, so cheap).
    for c in companies:
        if c["ok"]:
            row = u.by_symbol[c["symbol"]]
            res = load_financials(int(row["cik"]), contact_email=contact_email(request) or None)
            if res.ok:
                items.append((c["symbol"], res.financials))
    frame = comparison_frame(items)
    rows = []
    if not frame.empty:
        names = {c["symbol"]: c["name"] for c in companies}
        frame["company"] = [names.get(s, n) for s, n in zip(frame["symbol"], frame["company"])]
        frame["basis"] = ["IFRS" if t == "ifrs-full" else "US GAAP" for t in frame["taxonomy"]]
        rows = frame.to_dict("records")
    series = {}
    for sym, fin in items:
        df = annual_table(fin)
        series[sym] = [{"fiscal_year": int(r["fiscal_year"]), "period_end": r["period_end"], "revenue": r["revenue"],
                        "net_margin": r["net_margin"], "operating_margin": r["operating_margin"],
                        "revenue_growth": r["revenue_growth"]} for _, r in df.iterrows()]
    return ok({"symbols": wanted, "companies": companies, "rows": rows,
               "warnings": comparison_warnings(frame) if not frame.empty else [], "series": series},
              cache="no-store" if request.headers.get("x-sec-contact") else CACHE_PUBLIC)


def _csv(data: bytes, filename: str) -> Response:
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "public, max-age=60, s-maxage=1800"})


@app.get("/api/export/company/{symbol}.csv")
def export_company(symbol: str, request: Request):
    u = get_universe()
    row = u.by_symbol.get(symbol.upper())
    if (not row or row.get("cik") is None or (isinstance(row.get("cik"), float) and math.isnan(row["cik"]))
            or row.get("instrument_type") not in COMPANY_TYPES):
        return fail(404, "not_found", "No SEC financial statements for this symbol.")
    res = load_financials(int(row["cik"]), contact_email=contact_email(request) or None)
    if not res.ok:
        if res.error_kind in ("upstream", "config"):
            return fail(503, "upstream", MSG_DATA_UNAVAILABLE)
        return fail(404, "not_found", SAFE_COMPANY_MESSAGES.get(res.error_kind, "No annual data for this company."))
    return _csv(to_csv_bytes(long_format([(row["symbol"], res.financials)])), f"{row['symbol']}_financials_long.csv")


@app.get("/api/export/compare.csv")
def export_compare(request: Request, symbols: str = Query("", max_length=120)):
    u = get_universe()
    items = []
    for s in _parse_symbols(symbols):
        row = u.by_symbol.get(s)
        if not row or row.get("cik") is None or (isinstance(row.get("cik"), float) and math.isnan(row["cik"])):
            continue
        res = load_financials(int(row["cik"]), contact_email=contact_email(request) or None)
        if res.ok:
            items.append((s, res.financials))
    if not items:
        return fail(404, "not_found", "None of these symbols has annual SEC data.")
    return _csv(to_csv_bytes(long_format(items)), "fip_comparison_" + "_".join(s for s, _ in items) + ".csv")


class UploadIn(BaseModel):
    csv_text: str = Field(..., max_length=MAX_UPLOAD_BYTES)
    scale: str = Field("M", pattern="^(K|M|B|units)$")
    currency: str = Field("USD", max_length=3)
    name: str = Field("Uploaded company", max_length=60)


@app.post("/api/upload")
def upload(body: UploadIn):
    if body.currency not in CURRENCY_SYMBOLS:
        return fail(400, "bad_request", "Unsupported currency.")
    try:
        frame = read_user_csv(body.csv_text.encode("utf-8"), body.scale)
    except CsvImportError as exc:
        return fail(400, "bad_csv", f"Could not use this file: {exc}")
    fin = user_csv_to_financials(frame, body.currency, body.name.strip() or "Uploaded company")
    df = annual_table(fin)
    years = [{"fiscal_year": int(r["fiscal_year"]), "period_end": r["period_end"],
              "values": {k: r.get(k) for k in METRICS}, "ratios": {k: r.get(k) for k in RATIO_KEYS}}
             for _, r in df.iterrows()]
    return ok({"name": fin.entity_name, "currency": body.currency, "years": years, "warnings": list(fin.warnings),
               "insights": [i.__dict__ for i in generate_insights(df, body.currency, fin.warnings)]}, cache=None)


@app.get("/api/methodology")
def methodology():
    u = get_universe()
    return ok({
        "metrics": [{"key": s.key, "label": s.label, "statement": s.statement, "kind": s.kind,
                     "us_gaap": list(s.concepts.get("us-gaap", ())), "ifrs": list(s.concepts.get("ifrs-full", ())),
                     "description": s.description} for s in METRICS.values()],
        "ratios": [{"key": k, "label": v[0], "formula": v[1]} for k, v in RATIO_DEFINITIONS.items()],
        "forms": FORM_DESCRIPTIONS, "free_tier_models": list(FREE_TIER_MODELS), "default_models": list(DEFAULT_CHAIN),
        "sources": {"nasdaq_listed": NASDAQ_LISTED_URL, "other_listed": OTHER_LISTED_URL,
                    "sec_tickers": SEC_TICKERS_URL},
        "universe": {"built_at": str(u.meta.get("built_at", "")), "origin": u.origin,
                     "nasdaq_file_created": u.meta.get("nasdaq_file_created", ""),
                     "other_file_created": u.meta.get("other_file_created", "")},
    })


# ---------------------------------------------------------------- routes: assistant
_GUARD: AiGuard | None = None
_GUARD_LOCK = threading.Lock()


def guard() -> AiGuard:
    global _GUARD
    with _GUARD_LOCK:
        if _GUARD is None:
            _GUARD = AiGuard()
        return _GUARD


def client_ip(request: Request) -> str | None:
    """Vercel overwrites these headers at its edge, so they are trustworthy there. Elsewhere they are
    client-controlled and only honoured when the operator opts in (AI_TRUST_PROXY_HEADERS=true)."""
    if ON_VERCEL or config.get_bool_setting("AI_TRUST_PROXY_HEADERS", False):
        for header in ("x-real-ip", "x-vercel-forwarded-for", "x-forwarded-for"):
            value = (request.headers.get(header) or "").split(",")[0].strip()
            if value:
                return value
    return request.client.host if request.client else None


@app.get("/api/assistant/status")
def assistant_status(request: Request):
    g = guard()
    client = g.client_id(client_ip(request), None)
    status = g.status(client)
    models, rejected = resolve_models(config.get_setting("GEMINI_MODELS"))
    lim = g.limits
    return ok({"configured": config.gemini_configured(), "enabled": lim.enabled,
               "access_code_required": g.access_code_required(),
               "client_remaining": status.client_remaining, "client_limit": lim.client_per_day,
               "global_remaining": status.global_remaining, "global_limit": lim.global_per_day,
               "per_minute": lim.global_per_minute, "cooldown_seconds": lim.cooldown_seconds,
               "retry_after": status.retry_after, "models": models, "rejected_models": rejected,
               "max_question_chars": MAX_QUESTION_CHARS, "max_companies": MAX_COMPANIES, "presets": PRESETS},
              cache=None)


class AskIn(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=MAX_COMPANIES)
    question: str = Field(..., max_length=MAX_QUESTION_CHARS)
    access_code: str = Field("", max_length=128)


@app.post("/api/assistant/ask")
def assistant_ask(body: AskIn, request: Request):
    if not config.gemini_configured():
        return fail(503, "not_configured", MSG_ASSISTANT_OFF)
    g = guard()
    client = g.client_id(client_ip(request), None)
    if g.access_code_required():
        allowed, message = g.check_access_code(client, body.access_code)
        if not allowed:
            return fail(403, "access_code", message)
    if not body.question.strip():
        return fail(400, "bad_request", "Enter a research question.")
    payloads = _load_many(_parse_symbols(",".join(body.symbols))[:MAX_COMPANIES], request)
    u = get_universe()
    items, skipped = [], []
    for p in payloads:
        if p["status"] != "ok":
            skipped.append(p["symbol"])
            continue
        res = load_financials(int(u.by_symbol[p["symbol"]]["cik"]), contact_email=contact_email(request) or None)
        if res.ok:
            items.append((p["symbol"], res.financials))
        else:
            skipped.append(p["symbol"])
    if not items:
        return fail(400, "no_data", "None of the selected companies has annual SEC financial statements to analyze.")
    models, _ = resolve_models(config.get_setting("GEMINI_MODELS"))
    fact_pack = build_fact_pack(items)
    key = g.cache_key(fact_pack, body.question, models)
    cached = g.cached_answer(key)
    if cached:
        return ok({**cached, "from_cache": True, "skipped": skipped}, cache=None)
    decision = g.reserve(client)
    if not decision.allowed:
        return fail(429, "limit", decision.reason)
    try:
        # Stay well inside the serverless time limit: 20 s per call, 40 s for the whole model chain.
        answer = generate(fact_pack, body.question, config.gemini_api_key(), models=models, timeout=20, deadline=40)
    except GeminiError as exc:
        # Never the key, the question or the payload — only the failure category and Google's reason codes.
        if exc.kind == "auth":
            report("gemini_auth", "gemini", "Gemini rejected the server's API key", severity="critical",
                   temporary=False, threshold=1, detail=exc.user_message)
            return fail(503, "unavailable", MSG_SERVICE_UNAVAILABLE)
        if exc.kind in ("unavailable", "network"):
            report("gemini_outage", "gemini", "Gemini API unavailable or unreachable", severity="error",
                   threshold=2, detail=exc.user_message)
            return fail(503, "unavailable", MSG_ASSISTANT_DOWN)
        if exc.kind == "quota":
            report("gemini_quota", "gemini", "Free Gemini quota exhausted", severity="warning", threshold=1,
                   window_s=3600, detail=exc.user_message)
            return fail(429, "quota", MSG_ASSISTANT_QUOTA)
        log_event("info", "gemini_user_error", kind=exc.kind)
        return fail(400, exc.kind, exc.user_message)   # blocked / bad_request / empty: actionable for the visitor
    payload = {"text": answer.text, "model": answer.model, "symbols": [s for s, _ in items],
               "question": body.question, "fact_pack": fact_pack,
               "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    g.store_answer(key, payload)
    return ok({**payload, "from_cache": False, "skipped": skipped}, cache=None)


# ---------------------------------------------------------------- routes: filings, watchlist, screener
@app.get("/api/events/{symbol}")
def events_route(symbol: str, request: Request, all: bool = False, limit: int = Query(40, ge=1, le=100)):  # noqa: A002
    u = get_universe()
    sym = resolve_symbol(symbol)
    row = u.by_symbol.get(sym)
    if not row or entry_json(row)["cik"] is None:
        return fail(404, "not_found", "No SEC registrant for this symbol.")
    entry = entry_json(row)
    events, checked_at, error = load_events(entry["cik"], contact_email=contact_email(request) or None,
                                            limit=limit, include_noise=all)
    if error:
        report("sec_outage", "sec", "SEC filings feed could not be loaded", severity="warning", threshold=5,
               fingerprint="sec_outage:events", detail=error)
    return ok({"symbol": sym, "name": entry["name"], "events": [e.to_dict() for e in events],
               "checked_at": checked_at, "error": "The filing feed is unavailable right now." if error else ""},
              cache="no-store" if error else "public, max-age=60, s-maxage=600")


MAX_WATCHLIST = 15


@app.get("/api/watchlist")
def watchlist(request: Request, symbols: str = Query("", max_length=300)):
    u = get_universe()
    wanted = _parse_symbols(symbols, MAX_WATCHLIST)
    contact = contact_email(request) or None

    def one(sym):
        row = u.by_symbol.get(sym)
        if not row:
            return {"symbol": sym, "ok": False, "name": sym, "events": [], "error": "Not in current listings."}
        entry = entry_json(row)
        if entry["cik"] is None:
            return {"symbol": sym, "ok": False, "name": entry["name"], "events": [],
                    "error": "No SEC registrant for this listing."}
        events, checked_at, error = load_events(entry["cik"], contact_email=contact, limit=4)
        if error:
            report("sec_outage", "sec", "SEC filings feed could not be loaded", severity="warning", threshold=5,
                   fingerprint="sec_outage:events", detail=error)
        return {"symbol": sym, "ok": bool(events) or not error, "name": entry["name"], "exchange": entry["exchange"],
                "events": [e.to_dict() for e in events], "checked_at": checked_at,
                "error": "Filings are unavailable right now. Please try again later." if error else ""}
    with ThreadPoolExecutor(max_workers=4) as pool:
        items = list(pool.map(one, wanted))
    return ok({"items": items}, cache="public, max-age=60, s-maxage=600")


@app.get("/api/screener")
def screener(request: Request, year: int | None = Query(None, ge=2010, le=2100),
             sort: str = Query("revenue", max_length=30), order: str = Query("desc", pattern="^(asc|desc)$"),
             sector: list[str] = Query(default=[]), min_revenue: float = Query(0, ge=0),
             limit: int = Query(25, ge=1, le=50)):
    contact = contact_email(request) or None
    y = year or screener_mod.default_year()
    try:
        table = screener_mod.build_table(y, contact_email=contact)
        if table.empty and year is None:                  # newest year's frames not published yet
            y -= 1
            table = screener_mod.build_table(y, contact_email=contact)
    except DataSourceError as exc:
        report("sec_outage", "sec", "Screener could not load SEC frames", severity="error", threshold=2,
               fingerprint="sec_outage:screener", detail=exc.user_message)
        return fail(503, "upstream", MSG_DATA_UNAVAILABLE)
    sort_key = sort if sort in screener_mod.METRICS else "revenue"
    # Rank on frames, then verify a margin of extra candidates against each company's annual report.
    candidates, total, excluded = screener_mod.screen(table, get_universe().frame, sort=sort_key,
                                                      descending=order == "desc", sectors=sector,
                                                      min_revenue=min_revenue, limit=limit + 12)

    def loader(cik):
        res = load_financials(cik, contact_email=contact)
        return res.financials if res.ok else None
    checked = screener_mod.verify_rows(candidates, y, loader)
    if min_revenue > 0 and not checked.empty:
        checked = checked[checked["revenue"].fillna(0) >= min_revenue]
    rows, dropped = screener_mod.finalize(checked, sort=sort_key, descending=order == "desc", limit=limit)
    return ok({"year": y, "sort": sort_key, "order": order,
               "total": total, "excluded": excluded + dropped, "universe_size": int(len(table)),
               "verified": int(rows["verified"].sum()) if not rows.empty else 0,
               "corrected": int(rows["corrected"].sum()) if not rows.empty else 0,
               "rows": rows.to_dict("records"),
               "metrics": {k: {"label": v[0], "kind": v[1]} for k, v in screener_mod.METRICS.items()}},
              cache="public, max-age=300, s-maxage=21600, stale-while-revalidate=86400")



class ClientErrorIn(BaseModel):
    message: str = Field("", max_length=500)
    page: str = Field("", max_length=200)
    kind: str = Field("render", max_length=40)
    ref: str = Field("", max_length=20)


@app.post("/api/client-error")
def client_error(body: ClientErrorIn, request: Request):
    """Front-end crash reports (message and page only — no user data). Alerts only on repeated crashes."""
    report("frontend", "frontend", f"Front-end error on {body.page or '?'}: {body.message[:200]}", severity="error",
           threshold=3, window_s=600, fingerprint=f"frontend:{body.kind}:{body.message[:60]}", client_ref=body.ref)
    return ok({"ok": True}, cache=None)
