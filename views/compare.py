import pandas as pd
import streamlit as st

from fip.exports import long_format, to_csv_bytes
from fip.formatting import format_money, format_percent, is_missing
from fip.metrics import annual_table, comparison_frame, comparison_warnings
from fip.ui import charts
from fip.ui import components as ui
from fip.ui.state import MAX_COMPARE, company_bundles, display_unit, get_universe, option_label, years_shown

RATIO_METRICS = {
    "net_margin": "Net profit margin", "operating_margin": "Operating margin", "gross_margin": "Gross margin",
    "fcf_margin": "Free-cash-flow margin", "revenue_growth": "Revenue growth (YoY)",
    "revenue_cagr": "Revenue CAGR", "return_on_equity": "Return on equity",
    "liabilities_to_assets": "Liabilities / assets",
}
MONEY_METRICS = {"revenue": "Revenue", "net_income": "Net income", "operating_income": "Operating income",
                 "free_cash_flow": "Free cash flow", "total_assets": "Total assets"}


def main() -> None:
    universe = get_universe()
    ui.page_header("Company comparison", "Side-by-side fundamentals",
                   "Latest audited fiscal year for each company, with currency, period and accounting-basis checks.")

    options = list(universe.company_symbols)
    for s in st.session_state.get("compare", []):
        if s not in options:
            options.insert(0, s)
    st.multiselect("Companies (up to 6)", options, key="compare", max_selections=MAX_COMPARE,
                   format_func=lambda s: option_label(universe, s), placeholder="Type tickers or names")
    symbols = st.session_state.get("compare", [])
    if len(symbols) < 2:
        ui.empty_state("Pick at least two companies", "Use the box above or “Add to comparison” in the sidebar or "
                       "Company Explorer.", "⇄")
        return

    with st.spinner("Loading SEC filings…"):
        bundles = company_bundles(symbols)
    ok = [(b.symbol, b.result.financials) for b in bundles if b.has_financials]
    for b in bundles:
        if not b.has_financials:
            reason = b.result.error if b.result else ("No SEC registrant (CIK) is mapped to this listing."
                                                      if b.entry else "Not in current listings.")
            ui.notice(f"{b.symbol}: excluded — {reason}", "bad")
        elif b.result.notices:
            for n in b.result.notices:
                ui.notice(f"{b.symbol}: {n}")
    if len(ok) < 2:
        ui.empty_state("Not enough comparable data", "At least two companies need annual SEC financial statements.")
        return

    frame = comparison_frame(ok)
    for w in comparison_warnings(frame):
        ui.notice(w, "info")
    currencies = frame["currency"].unique()
    single_currency = len(currencies) == 1
    cur = currencies[0]
    unit = display_unit()

    header = ["Metric"] + [f"{r.symbol}" for r in frame.itertuples()]
    def row(label, values, cls="", fmt=None):
        cells = [label] + [fmt(v) if fmt else str(v) for v in values]
        neg = [False] + [isinstance(v, (int, float)) and not is_missing(v) and v < 0 for v in values]
        return {"cells": cells, "cls": cls, "neg": neg}

    money = lambda col: [format_money(v, c, unit=unit) for v, c in zip(frame[col], frame["currency"])]
    rows = [
        row("Company", frame["company"]),
        row("Fiscal year · form", [f"FY{fy} · {f}" for fy, f in zip(frame["fiscal_year"], frame["form"])]),
        row("Period end", frame["period_end"]),
        row("Currency · basis", [f"{c} · {'IFRS' if t == 'ifrs-full' else 'US GAAP'}"
                                 for c, t in zip(frame["currency"], frame["taxonomy"])]),
        {"cells": ["Revenue"] + money("revenue"), "neg": [False] + [v < 0 for v in frame["revenue"].fillna(0)]},
        {"cells": ["Operating income"] + money("operating_income"),
         "neg": [False] + [v < 0 for v in frame["operating_income"].fillna(0)]},
        {"cells": ["Net income"] + money("net_income"), "neg": [False] + [v < 0 for v in frame["net_income"].fillna(0)]},
        {"cells": ["Free cash flow (derived)"] + money("free_cash_flow"),
         "neg": [False] + [v < 0 for v in frame["free_cash_flow"].fillna(0)]},
        row("Revenue growth (YoY)", frame["revenue_growth"], "ratio", lambda v: format_percent(v, signed=True)),
        row("Revenue CAGR", [f"{format_percent(v, signed=True)} ({y}y)" if not is_missing(v) else "—"
                             for v, y in zip(frame["revenue_cagr"], frame["cagr_years"])], "ratio"),
        row("Gross margin", frame["gross_margin"], "ratio", format_percent),
        row("Operating margin", frame["operating_margin"], "ratio", format_percent),
        row("Net profit margin", frame["net_margin"], "ratio", format_percent),
        row("FCF margin", frame["fcf_margin"], "ratio", format_percent),
        row("Return on equity", frame["return_on_equity"], "ratio", format_percent),
        row("Liabilities / assets", frame["liabilities_to_assets"], "ratio", format_percent),
    ]
    ui.html_table(header, rows)
    st.caption("“—” means the company does not report that line item in its XBRL data (e.g. banks have no gross "
               "margin); it is never estimated. Ratios are currency-neutral.")

    st.write("")
    left, right = st.columns(2, gap="medium")
    with left:
        with st.container(border=True):
            metric = st.pills("Ratio", list(RATIO_METRICS), default="net_margin", key="cmp_ratio",
                              format_func=RATIO_METRICS.get) or "net_margin"
            st.plotly_chart(charts.comparison_bars(frame, metric, RATIO_METRICS[metric], kind="ratio"),
                            config=charts.PLOTLY_CONFIG, key="cmp_ratio_chart")
    with right:
        with st.container(border=True):
            metric = st.pills("Amount", list(MONEY_METRICS), default="revenue", key="cmp_money",
                              format_func=MONEY_METRICS.get) or "revenue"
            if single_currency:
                st.plotly_chart(charts.comparison_bars(frame, metric, MONEY_METRICS[metric], kind="money",
                                                       currency=cur, unit=unit),
                                config=charts.PLOTLY_CONFIG, key="cmp_money_chart")
            else:
                ui.empty_state("Different reporting currencies",
                               "Absolute amounts are not charted together because the companies report in "
                               + ", ".join(currencies) + ". Compare the ratio chart instead.", "¤")

    with st.container(border=True):
        ui.section("Trend", f"Last {years_shown()} fiscal years per company (each on its own fiscal calendar)")
        trend_metric = st.pills("Series", ["revenue", "net_margin", "operating_margin", "revenue_growth"],
                                default="revenue", key="cmp_trend",
                                format_func=lambda k: {"revenue": "Revenue", "net_margin": "Net margin",
                                                       "operating_margin": "Operating margin",
                                                       "revenue_growth": "Revenue growth"}[k]) or "revenue"
        series = {s: annual_table(f).tail(years_shown()) for s, f in ok}
        if trend_metric == "revenue" and not single_currency:
            ui.empty_state("Different reporting currencies", "Revenue trends need a common currency; choose a ratio.")
        else:
            kind = "money" if trend_metric == "revenue" else "ratio"
            label = {"revenue": "Revenue", "net_margin": "Net margin", "operating_margin": "Operating margin",
                     "revenue_growth": "Revenue growth"}[trend_metric]
            st.plotly_chart(charts.trend_comparison(series, trend_metric, label, kind=kind, currency=cur, unit=unit),
                            config=charts.PLOTLY_CONFIG, key="cmp_trend_chart")

    st.download_button("⬇ Download comparison data (CSV, full provenance)", to_csv_bytes(long_format(ok)),
                       file_name="fip_comparison_" + "_".join(s for s, _ in ok) + ".csv", mime="text/csv",
                       key="cmp_dl")
    st.caption("CSV values are in full reporting-currency units (not thousands or millions), one row per company × "
               "fiscal year × metric, with XBRL concept, form, filing date and accession number.")


main()
