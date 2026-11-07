"""Derived financial ratios, growth rates and comparison tables.

All ratios are returned as fractions (0.2692 = 26.92 %). Growth is computed only
between *consecutive* fiscal years (period ends 340–390 days apart) — never
across a gap or a fiscal-year-end change.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from fip.xbrl import METRICS, CompanyFinancials

VALUE_KEYS = [k for k in METRICS]
RATIO_DEFINITIONS = {
    "revenue_growth": ("Revenue growth (YoY)", "revenue_t / revenue_(t−1) − 1, consecutive fiscal years only"),
    "net_income_growth": ("Net income growth (YoY)", "net_income_t / net_income_(t−1) − 1; omitted if prior year ≤ 0"),
    "gross_margin": ("Gross margin", "gross_profit / revenue"),
    "operating_margin": ("Operating margin", "operating_income / revenue"),
    "net_margin": ("Net profit margin", "net_income / revenue"),
    "fcf_margin": ("Free-cash-flow margin", "free_cash_flow / revenue"),
    "cash_conversion": ("Cash conversion", "operating_cash_flow / net_income; omitted if net income ≤ 0"),
    "liabilities_to_assets": ("Liabilities / assets", "total_liabilities / total_assets"),
    "return_on_equity": ("Return on equity", "net_income / shareholders' equity (year-end); omitted if equity ≤ 0"),
    "net_margin_change": ("Net margin change", "net_margin_t − net_margin_(t−1), percentage points"),
    "operating_margin_change": ("Operating margin change", "operating_margin_t − operating_margin_(t−1), pp"),
}


def _safe_div(num, den, *, positive_den: bool = False):
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    valid = den > 0 if positive_den else den != 0
    return (num / den.where(valid)).astype(float)


def annual_table(fin: CompanyFinancials) -> pd.DataFrame:
    """One row per fiscal year: reported values (base units), derived ratios, and provenance."""
    rows = []
    for p in fin.periods:
        row = {
            "fiscal_year": p.fiscal_year, "period_start": p.start, "period_end": p.end, "form": p.form,
            "filed": p.filed, "accession": p.accession,
        }
        for key in VALUE_KEYS:
            fact = p.values.get(key)
            row[key] = np.nan if fact is None else fact.value
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    ends = pd.to_datetime(df["period_end"])
    gap_days = ends.diff().dt.days
    consecutive = gap_days.between(340, 390)
    df["consecutive"] = consecutive

    def yoy(col):
        # Growth off a zero or negative base is not meaningful, so it is omitted.
        prev = df[col].shift()
        return _safe_div(df[col] - prev, prev, positive_den=True).where(consecutive)

    df["revenue_growth"] = yoy("revenue")
    df["net_income_growth"] = yoy("net_income")
    df["gross_margin"] = _safe_div(df["gross_profit"], df["revenue"], positive_den=True)
    df["operating_margin"] = _safe_div(df["operating_income"], df["revenue"], positive_den=True)
    df["net_margin"] = _safe_div(df["net_income"], df["revenue"], positive_den=True)
    df["fcf_margin"] = _safe_div(df["free_cash_flow"], df["revenue"], positive_den=True)
    df["cash_conversion"] = _safe_div(df["operating_cash_flow"], df["net_income"], positive_den=True)
    df["liabilities_to_assets"] = _safe_div(df["total_liabilities"], df["total_assets"], positive_den=True)
    df["return_on_equity"] = _safe_div(df["net_income"], df["total_equity"], positive_den=True)
    df["net_margin_change"] = df["net_margin"].diff().where(consecutive)
    df["operating_margin_change"] = df["operating_margin"].diff().where(consecutive)
    return df


def cagr(first: float, last: float, years: float) -> float:
    if first is None or last is None or years <= 0 or not (first > 0 and last > 0):
        return float("nan")
    return (last / first) ** (1 / years) - 1


def revenue_cagr(df: pd.DataFrame, max_years: int = 5) -> tuple[float, int]:
    """Compound annual revenue growth over the longest unbroken run (≤ max_years)."""
    if df.empty or df["revenue"].isna().all():
        return float("nan"), 0
    sub = df.dropna(subset=["revenue"]).tail(max_years + 1)
    # Stop at the most recent gap so CAGR never spans a missing year.
    breaks = [i for i, ok in enumerate(sub["consecutive"].tolist()) if i > 0 and not ok]
    if breaks:
        sub = sub.iloc[breaks[-1]:]
    if len(sub) < 2:
        return float("nan"), 0
    years = len(sub) - 1
    return cagr(sub["revenue"].iloc[0], sub["revenue"].iloc[-1], years), years


def comparison_frame(items: list[tuple[str, CompanyFinancials]]) -> pd.DataFrame:
    """Latest fiscal year per company with headline ratios, for side-by-side comparison."""
    rows = []
    for label, fin in items:
        df = annual_table(fin)
        if df.empty:
            continue
        last = df.iloc[-1]
        growth, years = revenue_cagr(df)
        rows.append({
            "symbol": label, "company": fin.entity_name, "currency": fin.currency, "taxonomy": fin.taxonomy,
            "fiscal_year": int(last["fiscal_year"]), "period_end": last["period_end"], "form": last["form"],
            "revenue": last["revenue"], "net_income": last["net_income"],
            "operating_income": last["operating_income"], "free_cash_flow": last["free_cash_flow"],
            "total_assets": last["total_assets"],
            "revenue_growth": last["revenue_growth"], "revenue_cagr": growth, "cagr_years": years,
            "gross_margin": last["gross_margin"], "operating_margin": last["operating_margin"],
            "net_margin": last["net_margin"], "fcf_margin": last["fcf_margin"],
            "liabilities_to_assets": last["liabilities_to_assets"], "return_on_equity": last["return_on_equity"],
        })
    return pd.DataFrame(rows)


def comparison_warnings(frame: pd.DataFrame, today: date | None = None) -> list[str]:
    warnings = []
    if frame.empty or len(frame) < 2:
        return warnings
    currencies = sorted(frame["currency"].unique())
    if len(currencies) > 1:
        warnings.append("Companies report in different currencies (" + ", ".join(currencies) + "). Absolute amounts "
                        "are not converted and must not be compared directly; ratios are currency-neutral.")
    ends = pd.to_datetime(frame["period_end"])
    spread = (ends.max() - ends.min()).days
    if spread > 31:
        warnings.append(f"Latest fiscal years end on different dates (spread of {spread} days). Periods are the "
                        "companies' own fiscal years, not identical calendar periods.")
    if frame["taxonomy"].nunique() > 1:
        warnings.append("Some companies report under IFRS and others under US GAAP; line items are defined differently.")
    return warnings
