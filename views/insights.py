import streamlit as st

from fip.exports import CsvImportError, read_user_csv, to_csv_bytes, user_csv_to_financials
from fip.formatting import CURRENCY_SYMBOLS, format_money, format_percent
from fip.insights import CALCULATION, FACT, FLAG, generate_insights
from fip.metrics import annual_table
from fip.ui import charts
from fip.ui import components as ui
from fip.ui.company import load_company_context
from fip.ui.state import display_unit

SAMPLE_CSV = (
    "fiscal_year,revenue,net_income,operating_income,operating_cash_flow,capex\n"
    "2022,100,12,15,18,6\n2023,115,14,17,21,7\n2024,130,18,22,26,8\n2025,142,21,25,29,9\n"
)


def _render_insights(items, key: str) -> None:
    choice = st.segmented_control("Show", ["All", FACT, CALCULATION, FLAG], default="All", key=key) or "All"
    shown = [i for i in items if choice == "All" or i.category == choice]
    left, right = st.columns(2, gap="medium")
    for n, item in enumerate(shown):
        with (left if n % 2 == 0 else right):
            ui.insight_card(item)


def _company_tab() -> None:
    ctx = load_company_context()
    if ctx is None:
        return
    items = generate_insights(ctx.full, ctx.fin.currency, ctx.fin.warnings)
    st.caption("Facts are reported values. Calculations show their formula. Flags highlight data caveats or patterns "
               "worth checking in the filing. No forecasts, valuations or recommendations.")
    _render_insights(items, "ins_filter")


def _upload_tab() -> None:
    ui.section("Analyze your own CSV", "Same calculations as SEC data; your figures are processed in memory only.")
    c1, c2, c3 = st.columns([1.4, 1, 1])
    with c1:
        uploaded = st.file_uploader("CSV file (max 1 MB)", type=["csv"], key="up_file")
    with c2:
        scale = st.selectbox("Values in the file are in", ["M", "K", "B", "units"], key="up_scale",
                             format_func={"M": "Millions", "K": "Thousands", "B": "Billions", "units": "Full units"}.get)
    with c3:
        currency = st.selectbox("Currency", list(CURRENCY_SYMBOLS), key="up_cur")
    name = st.text_input("Label", value="Uploaded company", max_chars=60, key="up_name")
    st.download_button("⬇ Sample CSV template", SAMPLE_CSV.encode(), file_name="fip_sample_financials.csv",
                       mime="text/csv", key="up_sample")
    st.caption("Required columns: fiscal_year (or year), revenue, net_income. Optional: operating_income, "
               "gross_profit, operating_cash_flow, capex, total_assets, total_liabilities, total_equity.")
    if uploaded is None:
        return
    try:
        frame = read_user_csv(uploaded.getvalue(), scale)
    except CsvImportError as exc:
        ui.notice(f"Could not use this file: {exc}", "bad")
        return
    fin = user_csv_to_financials(frame, currency, name.strip() or "Uploaded company")
    df = annual_table(fin)
    last = df.iloc[-1]
    ui.kpi_grid([
        ui.Kpi("Revenue", format_money(last["revenue"], currency, unit=display_unit()),
               format_percent(last["revenue_growth"], signed=True) + " YoY" if last["revenue_growth"] == last["revenue_growth"] else "",
               "up" if (last["revenue_growth"] or 0) > 0 else "down", f"FY{int(last['fiscal_year'])}"),
        ui.Kpi("Net income", format_money(last["net_income"], currency, unit=display_unit()), accent="var(--cyan)"),
        ui.Kpi("Net margin", format_percent(last["net_margin"]), accent="var(--amber)"),
    ])
    st.plotly_chart(charts.money_bars(df, [("revenue", "Revenue"), ("net_income", "Net income")], currency,
                                      display_unit()), config=charts.PLOTLY_CONFIG, key="up_chart")
    _render_insights(generate_insights(df, currency, fin.warnings), "up_filter")
    export = df.drop(columns=["accession", "filed", "form"]).assign(currency=currency, unit="full units")
    st.download_button("⬇ Prepared data with ratios (CSV)", to_csv_bytes(export), file_name="fip_uploaded_analysis.csv",
                       mime="text/csv", key="up_dl")


def main() -> None:
    ui.page_header("Financial insights", "Transparent, rule-based analysis",
                   "Every observation states its rule and evidence. Works without AI.")
    tab_company, tab_upload = st.tabs(["Selected company", "Upload your own CSV"])
    with tab_company:
        _company_tab()
    with tab_upload:
        _upload_tab()


main()
