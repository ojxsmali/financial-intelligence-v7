"""Market screener: rank every SEC filer by a fundamental, using SEC XBRL "frames".

A frame (``data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/CY{year}.json``) holds one value per
company for one concept and one calendar period — every filer in a single request. SEC assigns
each company's reported annual period to the calendar year it best aligns with, so screener
figures are *calendar-aligned* and can differ slightly from a company's own fiscal-year view.

Revenue uses the largest of the main total-revenue concepts per company (same rule as company
pages). Ratios are computed only from positive denominators. Nothing is estimated.
"""
from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from fip.config import cache_dir
from fip.http_client import DataSourceError, NotFoundError, fetch

FRAME_TTL = 24 * 3600
REVENUE_TAGS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax")
METRICS = {
    "revenue": ("Revenue", "money"),
    "net_income": ("Net income", "money"),
    "net_margin": ("Net profit margin", "ratio"),
    "revenue_growth": ("Revenue growth", "ratio"),
    "total_assets": ("Total assets", "money"),
    "return_on_assets": ("Return on assets", "ratio"),
}
# Ratios outside these bounds are almost always a scale error in a filer's tagging (e.g. a value
# reported in thousands next to one in units). They are excluded from ranking and counted, not shown.
PLAUSIBLE = {"net_margin": (-10.0, 1.0), "return_on_assets": (-10.0, 1.0)}


def frame_url(tag: str, period: str) -> str:
    return f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"


def load_frame(tag: str, period: str, *, contact_email: str | None = None, fetcher=None) -> dict[int, float]:
    """{cik: value} for one frame. Cached 24 h on disk; {} if SEC has no such frame yet."""
    directory = cache_dir() / "frames"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{tag}_{period}.json"
    if path.exists() and time.time() - path.stat().st_mtime < FRAME_TTL:
        try:
            return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
        except (OSError, ValueError):
            pass
    try:
        raw = json.loads((fetcher or fetch)(frame_url(tag, period), sec=True, contact_email=contact_email).content)
    except NotFoundError:
        return {}
    except (DataSourceError, ValueError):
        if path.exists():           # stale copy beats nothing
            return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
        raise
    values = {}
    for row in raw.get("data", []):
        try:
            v = float(row["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(v):
            values[int(row["cik"])] = v
    try:
        tmp = path.with_suffix(f".{time.time_ns()}.tmp")
        tmp.write_text(json.dumps(values), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
    return values


def default_year(today: date | None = None) -> int:
    """Latest calendar year whose annual reports are essentially all filed (10-Ks are due within ~90 days)."""
    today = today or date.today()
    return today.year - 1 if today.month >= 5 else today.year - 2


def build_table(year: int, *, contact_email: str | None = None, fetcher=None) -> pd.DataFrame:
    jobs = {("rev", year, t): (t, f"CY{year}") for t in REVENUE_TAGS}
    jobs.update({("rev", year - 1, t): (t, f"CY{year - 1}") for t in REVENUE_TAGS})
    jobs[("ni",)] = ("NetIncomeLoss", f"CY{year}")
    jobs[("assets",)] = ("Assets", f"CY{year}Q4I")
    # Six independent SEC requests: fetch them in parallel (the shared rate limiter still applies).
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {k: pool.submit(load_frame, tag, period, contact_email=contact_email, fetcher=fetcher)
                   for k, (tag, period) in jobs.items()}
        frames = {k: f.result() for k, f in futures.items()}

    def revenue(y):
        merged: dict[int, float] = {}
        for tag in REVENUE_TAGS:
            for cik, v in frames[("rev", y, tag)].items():
                merged[cik] = max(merged.get(cik, v), v)
        return merged

    rev, rev_prev = revenue(year), revenue(year - 1)
    ni = frames[("ni",)]
    assets = frames[("assets",)]
    ciks = set(rev) | set(ni) | set(assets)
    rows = []
    for cik in ciks:
        r, n, a, rp = rev.get(cik), ni.get(cik), assets.get(cik), rev_prev.get(cik)
        rows.append({
            "cik": cik, "revenue": r, "net_income": n, "total_assets": a,
            "net_margin": n / r if n is not None and r and r > 0 else None,
            "revenue_growth": r / rp - 1 if r is not None and rp and rp > 0 else None,
            "return_on_assets": n / a if n is not None and a and a > 0 else None,
        })
    return pd.DataFrame(rows, columns=["cik", "revenue", "net_income", "total_assets", "net_margin",
                                       "revenue_growth", "return_on_assets"])


def screen(table: pd.DataFrame, universe: pd.DataFrame, *, sort: str = "revenue", descending: bool = True,
           sectors=None, min_revenue: float = 0.0, limit: int = 50) -> tuple[pd.DataFrame, int, int]:
    """Join the frame table to listed operating companies, filter, sort.
    Returns (top rows, total matches, rows excluded as implausible)."""
    if sort not in METRICS:
        sort = "revenue"
    companies = universe[universe["is_company"] & universe["cik"].notna()].copy()
    companies["cik"] = companies["cik"].astype(int)
    # One row per registrant: prefer the primary common-stock listing (shortest symbol).
    companies = (companies.assign(_len=companies["symbol"].str.len())
                 .sort_values(["cik", "_len", "symbol"]).drop_duplicates("cik"))
    df = table.merge(companies[["cik", "symbol", "name", "exchange", "sector"]], on="cik", how="inner")
    if sectors:
        df = df[df["sector"].isin(sectors)]
    if min_revenue > 0:
        df = df[df["revenue"].fillna(0) >= min_revenue]
    df = df[df[sort].notna()]
    excluded = 0
    if sort in PLAUSIBLE:
        lo, hi = PLAUSIBLE[sort]
        ok = df[sort].between(lo, hi)
        excluded = int((~ok).sum())
        df = df[ok]
    total = len(df)
    df = df.sort_values(sort, ascending=not descending).head(max(1, min(limit, 200)))
    return df.reset_index(drop=True), total, excluded


def _period_for_year(fin, year: int):
    """The company's annual period SEC would align to calendar `year`: the one whose midpoint falls in it."""
    best = None
    for p in fin.periods:
        try:
            start, end = date.fromisoformat(p.start), date.fromisoformat(p.end)
        except (TypeError, ValueError):
            continue
        mid = start + (end - start) / 2
        if mid.year == year:
            best = p
    return best


def verify_rows(rows: pd.DataFrame, year: int, loader, *, workers: int = 4) -> pd.DataFrame:
    """Cross-check frame figures against each company's own annual report and correct them.

    SEC frames occasionally carry a mistagged fact from a later filing (e.g. one quarter labelled as a
    full year). For the rows we are about to show, the company-page extraction — the trusted source —
    replaces revenue, net income and assets and the ratios are recomputed. ``loader(cik)`` returns
    CompanyFinancials or None. Rows that can't be checked keep frame values with verified=False.
    """
    from fip.metrics import annual_table

    def check(row):
        out = dict(row)
        out.update(verified=False, fiscal_year=None, corrected=False)
        try:
            fin = loader(int(row["cik"]))
        except Exception:      # a single company's failure must not break the screener
            fin = None
        if fin is None or fin.currency != "USD":
            # Frames are USD-only; a company reporting in another currency (e.g. Trip.com in CNY) can't be
            # cross-checked without converting currencies, which this app never does.
            return out
        period = _period_for_year(fin, year)
        if period is None:
            return out
        df = annual_table(fin)
        match = df[df["period_end"] == period.end]
        if match.empty:
            return out
        r = match.iloc[-1]

        def val(k):
            v = r.get(k)
            return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)
        rev, ni, assets, growth = val("revenue"), val("net_income"), val("total_assets"), val("revenue_growth")
        before = (out.get("revenue"), out.get("net_income"))
        out.update(revenue=rev, net_income=ni, total_assets=assets, revenue_growth=growth,
                   net_margin=ni / rev if ni is not None and rev and rev > 0 else None,
                   return_on_assets=ni / assets if ni is not None and assets and assets > 0 else None,
                   verified=True, fiscal_year=int(r["fiscal_year"]))
        def differs(a, b):
            return a is not None and b is not None and abs(a - b) > 0.02 * max(abs(a), abs(b), 1.0)
        out["corrected"] = differs(before[0], rev) or differs(before[1], ni)
        return out

    if rows.empty:
        return rows.assign(verified=pd.Series(dtype=bool), fiscal_year=pd.Series(dtype=object),
                           corrected=pd.Series(dtype=bool))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        checked = list(pool.map(check, rows.to_dict("records")))
    return pd.DataFrame(checked)


def finalize(candidates: pd.DataFrame, *, sort: str, descending: bool, limit: int) -> tuple[pd.DataFrame, int]:
    """Re-rank verified candidates; drop rows whose corrected metric is missing or implausible."""
    df = candidates[candidates[sort].notna()]
    dropped = len(candidates) - len(df)
    if sort in PLAUSIBLE:
        lo, hi = PLAUSIBLE[sort]
        ok = df[sort].between(lo, hi)
        dropped += int((~ok).sum())
        df = df[ok]
    return df.sort_values(sort, ascending=not descending).head(limit).reset_index(drop=True), dropped
