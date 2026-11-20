import streamlit as st

from fip.formatting import format_money, format_per_share, format_percent, format_pp, is_missing
from fip.insights import generate_insights
from fip.metrics import revenue_cagr
from fip.ui import charts
from fip.ui import components as ui
from fip.ui.company import freshness_line, load_company_context
from fip.ui.state import display_unit, get_universe
from fip.universe import share_classes


def _direction(value) -> str:
    if is_missing(value) or value == 0:
        return "flat"
    return "up" if value > 0 else "down"


def main() -> None:
    ui.page_header("Overview", "Annual performance",
                   "Audited annual results from SEC filings: revenue, profitability, cash generation and balance sheet.")
    ctx = load_company_context()
    if ctx is None:
        return
    fin, df = ctx.fin, ctx.df
    cur = fin.currency
    unit = display_unit()
    last = df.iloc[-1]
    prev_fy = f"FY{int(df.iloc[-2]['fiscal_year'])}" if len(df) > 1 else "prior year"
    fy = f"FY{int(last['fiscal_year'])}"
    foot = f"{fy} · {last['form']}"

    def money(v):
        return format_money(v, cur, unit=unit)

    growth = last["revenue_growth"]
    cagr, years = revenue_cagr(ctx.full)
    kpis = [
        ui.Kpi("Revenue", money(last["revenue"]), format_percent(growth, signed=True) + " YoY" if not is_missing(growth)
               else "YoY n/a", _direction(growth), foot,
               f"Reported total revenue for the fiscal year ended {last['period_end']}. Growth vs {prev_fy}.",
               available=not is_missing(last["revenue"])),
        ui.Kpi("Net income", money(last["net_income"]),
               format_percent(last["net_income_growth"], signed=True) + " YoY"
               if not is_missing(last["net_income_growth"]) else "", _direction(last["net_income_growth"]), foot,
               "Net income attributable to the parent company (reported).",
               available=not is_missing(last["net_income"])),
        ui.Kpi("Net profit margin", format_percent(last["net_margin"]), format_pp(last["net_margin_change"])
               if not is_missing(last["net_margin_change"]) else "", _direction(last["net_margin_change"]), foot,
               "Net income ÷ revenue. Change shown in percentage points.",
               available=not is_missing(last["net_margin"])),
        ui.Kpi("Operating margin", format_percent(last["operating_margin"]) if not is_missing(last["operating_margin"])
               else "Not reported", format_pp(last["operating_margin_change"])
               if not is_missing(last["operating_margin_change"]) else "", _direction(last["operating_margin_change"]),
               foot, "Operating income ÷ revenue. Banks and insurers often do not report operating income.",
               available=not is_missing(last["operating_margin"])),
        ui.Kpi("Free cash flow", money(last["free_cash_flow"]) if not is_missing(last["free_cash_flow"])
               else "Not available", format_percent(last["fcf_margin"]) + " of revenue"
               if not is_missing(last["fcf_margin"]) else "", "flat", "derived",
               "Derived: operating cash flow − capital expenditure (purchases of PP&E).",
               available=not is_missing(last["free_cash_flow"])),
        ui.Kpi(f"{years}-yr revenue CAGR" if years else "Revenue CAGR",
               format_percent(cagr, signed=True) if not is_missing(cagr) else "n/a", "", "flat",
               f"FY{int(ctx.full.iloc[-years - 1]['fiscal_year'])}–{fy}" if years else "",
               "Compound annual growth over the longest unbroken run of fiscal years (max 5).",
               available=not is_missing(cagr)),
    ]
    ui.kpi_grid(kpis)

    classes = [s for s in share_classes(get_universe().frame, ctx.bundle.entry.get("cik")) if s != ctx.bundle.symbol]
    if classes:
        st.caption(f"Same SEC registrant also trades as: {', '.join(classes)}. Financial statements cover the whole "
                   "company, not one share class.")

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        ui.section("Revenue and profit", "Reported annual figures; one scale for all bars")
        charts.show(charts.money_bars(df, [("revenue", "Revenue"), ("operating_income", "Operating income"),
                                           ("net_income", "Net income")], cur, unit, title="Revenue and profit"))
    with right:
        ui.section("Margin profile", "Share of revenue by fiscal year")
        charts.show(charts.ratio_lines(df, [("gross_margin", "Gross"), ("operating_margin", "Operating"),
                                            ("net_margin", "Net"), ("fcf_margin", "Free cash flow")],
                                       title="Margin profile"))

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        ui.section("Cash generation", "Operating cash flow, capital expenditure and derived free cash flow")
        charts.show(charts.money_bars(df, [("operating_cash_flow", "Operating cash flow"), ("capex", "Capex"),
                                           ("free_cash_flow", "Free cash flow")], cur, unit, title="Cash generation"))
    with right:
        ui.section("Key observations", "Rule-based calculations and flags — not AI-generated")
        items = [i for i in generate_insights(ctx.full, cur) if i.category != "Fact"][:4]
        for item in items:
            ui.insight_card(item)
        st.page_link("views/insights.py", label="All insights and their rules", icon=":material/arrow_forward:")

    ui.section("Balance sheet", f"As of {last['period_end']} ({fy} {last['form']})")
    ui.kpi_grid([
        ui.Kpi("Total assets", money(last["total_assets"]), available=not is_missing(last["total_assets"])),
        ui.Kpi("Total liabilities", money(last["total_liabilities"]),
               foot=f"{format_percent(last['liabilities_to_assets'])} of assets"
               if not is_missing(last["liabilities_to_assets"]) else "",
               available=not is_missing(last["total_liabilities"])),
        ui.Kpi("Shareholders' equity", money(last["total_equity"]), available=not is_missing(last["total_equity"])),
        ui.Kpi("Cash", money(last["cash"]) if "cash" in last else "—",
               available="cash" in last and not is_missing(last["cash"])),
        ui.Kpi("Diluted EPS", format_per_share(last["eps_diluted"], cur), foot="per share, reported",
               available=not is_missing(last["eps_diluted"])),
        ui.Kpi("Return on equity", format_percent(last["return_on_equity"]), foot="net income / year-end equity",
               available=not is_missing(last["return_on_equity"])),
    ])

    if fin.warnings:
        with st.expander(f"Data notes ({len(fin.warnings)})"):
            for w in fin.warnings:
                st.markdown(f"- {w}")
    freshness_line(ctx)


main()
