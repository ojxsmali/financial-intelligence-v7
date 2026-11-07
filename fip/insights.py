"""Transparent, rule-based financial observations.

Every insight states its rule, the numbers it used and the fiscal year(s) they
come from. Nothing here is a forecast, valuation or recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from fip.formatting import format_money, format_percent, format_pp, is_missing
from fip.metrics import revenue_cagr

FACT, CALCULATION, FLAG = "Fact", "Calculation", "Flag"


@dataclass
class Insight:
    category: str        # Fact | Calculation | Flag
    tone: str            # positive | negative | neutral | caution
    title: str
    detail: str
    rule: str
    evidence: str        # fiscal years / filings used


def _fy(row) -> str:
    return f"FY{int(row['fiscal_year'])}"


def generate_insights(df: pd.DataFrame, currency: str, warnings: list[str] | None = None) -> list[Insight]:
    out: list[Insight] = []
    if df is None or df.empty:
        return [Insight(FLAG, "caution", "No annual data", "No audited annual figures are available.", "—", "—")]
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None
    fy = _fy(last)
    src = f"{fy} {last['form']} filed {last['filed']}"

    if not is_missing(last["revenue"]):
        out.append(Insight(FACT, "neutral", f"{fy} revenue: {format_money(last['revenue'], currency)}",
                           f"Reported revenue for the fiscal year ended {last['period_end']}.",
                           "Reported value", src))
    if not is_missing(last.get("revenue_growth")):
        g = last["revenue_growth"]
        tone = "positive" if g > 0 else "negative" if g < 0 else "neutral"
        verb = "grew" if g > 0 else "declined" if g < 0 else "was flat"
        out.append(Insight(CALCULATION, tone, f"Revenue {verb} {format_percent(abs(g))} year over year",
                           f"{format_money(prev['revenue'], currency)} in {_fy(prev)} → "
                           f"{format_money(last['revenue'], currency)} in {fy}.",
                           "revenue_t / revenue_(t−1) − 1", f"{_fy(prev)}–{fy}"))
    elif prev is not None:
        out.append(Insight(FLAG, "caution", "Year-over-year growth not computed",
                           "The two latest fiscal years are not consecutive or the prior revenue was not positive.",
                           "Growth requires consecutive fiscal years", f"{_fy(prev)}, {fy}"))

    growth, years = revenue_cagr(df)
    if not is_missing(growth) and years >= 2:
        first = df.dropna(subset=["revenue"]).iloc[-(years + 1)]
        out.append(Insight(CALCULATION, "positive" if growth > 0 else "negative",
                           f"{years}-year revenue CAGR: {format_percent(growth, signed=True)}",
                           f"Compound annual growth from {_fy(first)} to {fy}.",
                           "(revenue_end / revenue_start)^(1/years) − 1", f"{_fy(first)}–{fy}"))

    if not is_missing(last.get("net_margin")):
        change = last.get("net_margin_change")
        detail = f"Net income {format_money(last['net_income'], currency)} on revenue {format_money(last['revenue'], currency)}."
        if not is_missing(change):
            detail += f" Change vs {_fy(prev)}: {format_pp(change)}."
        tone = "negative" if last["net_margin"] < 0 else "neutral"
        out.append(Insight(CALCULATION, tone, f"Net profit margin {format_percent(last['net_margin'])}", detail,
                           "net_income / revenue", src))

    if not is_missing(last.get("operating_margin")):
        change = last.get("operating_margin_change")
        detail = "Operating income excludes interest, taxes and non-operating gains or losses."
        if not is_missing(change):
            detail += f" Change vs {_fy(prev)}: {format_pp(change)}."
        out.append(Insight(CALCULATION, "neutral", f"Operating margin {format_percent(last['operating_margin'])}",
                           detail, "operating_income / revenue", src))
        gap = last["net_income"] - last["operating_income"] if not is_missing(last["net_income"]) else None
        if gap is not None and last["operating_income"] > 0 and gap > 0.1 * abs(last["operating_income"]):
            out.append(Insight(FLAG, "caution", "Net income exceeds operating income",
                               f"Net income is {format_money(gap, currency)} above operating income, which points to "
                               "non-operating items (investment gains, tax benefits or other income). Reported "
                               "profitability overstates operating profitability for this year.",
                               "net_income − operating_income > 10 % of operating income", src))
    elif not is_missing(last.get("revenue")):
        out.append(Insight(FLAG, "neutral", "Operating income not reported",
                           "The filing does not tag an operating-income subtotal (common for banks and insurers). "
                           "Operating margin is therefore unavailable rather than estimated.",
                           "OperatingIncomeLoss / ProfitLossFromOperatingActivities absent", src))

    if not is_missing(last.get("free_cash_flow")):
        fcf = last["free_cash_flow"]
        out.append(Insight(CALCULATION, "positive" if fcf > 0 else "negative",
                           f"Free cash flow {format_money(fcf, currency)}",
                           f"Operating cash flow {format_money(last['operating_cash_flow'], currency)} minus capital "
                           f"expenditure {format_money(last['capex'], currency)}.",
                           "operating_cash_flow − capex (derived)", src))
    conv = last.get("cash_conversion")
    if not is_missing(conv):
        if conv < 0.8:
            out.append(Insight(FLAG, "caution", f"Cash conversion {conv:.2f}×",
                               "Operating cash flow is materially below net income; earnings were less backed by cash "
                               "this year (working-capital build, non-cash gains, or timing).",
                               "operating_cash_flow / net_income < 0.8", src))
        elif conv > 1.2:
            out.append(Insight(CALCULATION, "positive", f"Cash conversion {conv:.2f}×",
                               "Operating cash flow exceeds net income (non-cash charges such as depreciation and "
                               "stock compensation are added back).", "operating_cash_flow / net_income", src))

    lta = last.get("liabilities_to_assets")
    if not is_missing(lta):
        tone = "caution" if lta > 0.85 else "neutral"
        note = " Very high leverage is structural for banks and insurers." if lta > 0.85 else ""
        out.append(Insight(CALCULATION, tone, f"Liabilities equal {format_percent(lta)} of assets",
                           f"Total liabilities {format_money(last['total_liabilities'], currency)} vs total assets "
                           f"{format_money(last['total_assets'], currency)}.{note}",
                           "total_liabilities / total_assets", f"{fy} balance sheet"))

    if not is_missing(last.get("net_income")) and last["net_income"] < 0:
        out.append(Insight(FLAG, "negative", "Net loss reported", f"{fy} net income was negative.",
                           "net_income < 0", src))

    for w in warnings or []:
        out.append(Insight(FLAG, "caution", "Data consistency note", w, "Automated data validation", "XBRL record"))
    out.append(Insight(FLAG, "neutral", "Scope of these observations",
                       "Figures come from audited annual statements in SEC XBRL data. They cannot explain causes, "
                       "segment mix or one-time items without reading the filing's notes and MD&A.",
                       "Methodology", "—"))
    return out
