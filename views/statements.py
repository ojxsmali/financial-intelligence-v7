import pandas as pd
import streamlit as st

from fip.exports import long_format, to_csv_bytes
from fip.formatting import SCALES, format_money, format_per_share, format_percent, is_missing, resolve_unit
from fip.metrics import RATIO_DEFINITIONS
from fip.ui import components as ui
from fip.ui.company import freshness_line, load_company_context
from fip.ui.state import display_unit
from fip.xbrl import METRICS

STATEMENTS = {
    "income": [("revenue", ""), ("cost_of_revenue", "sub"), ("gross_profit", ""), ("operating_income", ""),
               ("net_income", ""), ("eps_diluted", "sub")],
    "balance": [("total_assets", ""), ("total_liabilities", ""), ("total_equity", ""), ("cash", "sub")],
    "cashflow": [("operating_cash_flow", ""), ("capex", "sub"), ("free_cash_flow", "")],
}
RATIOS = ["revenue_growth", "gross_margin", "operating_margin", "net_margin", "fcf_margin", "cash_conversion",
          "liabilities_to_assets", "return_on_equity"]


def _statement(ctx, keys, unit: str):
    fin, df = ctx.fin, ctx.df
    periods = {p.end: p for p in fin.periods}
    money_values = [df[k].abs().max() for k, _ in keys if k != "eps_diluted" and k in df]
    # One scale for the whole table so every row is directly comparable.
    scale_key = resolve_unit(money_values, unit)
    header = [f"{fin.currency} · {SCALES[scale_key][2]}"] + [f"FY{int(y)}" for y in df["fiscal_year"]]
    rows = []
    for key, cls in keys:
        spec = METRICS[key]
        cells, negs, marks = [spec.label], [False], [""]
        for _, r in df.iterrows():
            fact = periods[r["period_end"]].values.get(key)
            if fact is None:
                cells.append("—"); negs.append(False); marks.append("")
                continue
            if key == "eps_diluted":
                cells.append(format_per_share(fact.value, fin.currency))
            else:
                cells.append(format_money(fact.value, fin.currency, unit=scale_key))
            negs.append(fact.value < 0)
            note = []
            if fact.derived:
                note.append(f"Derived: {fact.formula}")
            if fact.restated:
                note.append(f"Revised in a later filing (originally {format_money(fact.original_value, fin.currency)})")
            marks.append("; ".join(note))
        rows.append({"cells": cells, "cls": cls, "neg": negs, "marks": marks})
    ui.html_table(header, rows)
    st.caption("● marks derived or later-revised values (hover for details). “—” = not reported in XBRL; never estimated.")


def _wide_csv(ctx, keys) -> bytes:
    fin = ctx.fin
    out = pd.DataFrame({"metric": [METRICS[k].label for k, _ in keys]})
    for _, r in ctx.df.iterrows():
        out[f"FY{int(r['fiscal_year'])} ({r['period_end']})"] = [r[k] for k, _ in keys]
    out.insert(1, "unit", [f"{fin.currency}/share" if k == "eps_diluted" else f"{fin.currency} (full units)"
                           for k, _ in keys])
    return to_csv_bytes(out)


def main() -> None:
    ui.page_header("Financial statements", "Income statement, balance sheet & cash flow",
                   "Annual figures from 10-K / 20-F / 40-F XBRL data. Each column is the company's own fiscal year.")
    ctx = load_company_context()
    if ctx is None:
        return
    unit = display_unit()
    tabs = st.tabs(["Income statement", "Balance sheet", "Cash flow", "Ratios", "XBRL concept map"])
    names = {"income": "income_statement", "balance": "balance_sheet", "cashflow": "cash_flow"}
    for tab, key in zip(tabs[:3], ("income", "balance", "cashflow")):
        with tab:
            _statement(ctx, STATEMENTS[key], unit)
            st.download_button(f"⬇ {names[key].replace('_', ' ').title()} (CSV)", _wide_csv(ctx, STATEMENTS[key]),
                               file_name=f"{ctx.bundle.symbol}_{names[key]}.csv", mime="text/csv", key=f"dl_{key}")
    with tabs[3]:
        df = ctx.df
        header = ["Ratio"] + [f"FY{int(y)}" for y in df["fiscal_year"]]
        rows = []
        for key in RATIOS:
            label, _ = RATIO_DEFINITIONS[key]
            if key == "cash_conversion":
                cells = [f"{v:.2f}×" if not is_missing(v) else "—" for v in df[key]]
            else:
                cells = [format_percent(v, signed=key.endswith("growth")) for v in df[key]]
            rows.append({"cells": [label] + cells, "cls": "ratio",
                         "neg": [False] + [not is_missing(v) and v < 0 for v in df[key]]})
        ui.html_table(header, rows)
        with st.expander("Formulas"):
            for key in RATIOS:
                label, formula = RATIO_DEFINITIONS[key]
                st.markdown(f"- **{label}** — `{formula}`")
    with tabs[4]:
        fin = ctx.fin
        records = []
        for p in fin.periods[-len(ctx.df):]:
            for key, fact in p.values.items():
                records.append({"Fiscal year": f"FY{p.fiscal_year}", "Metric": METRICS[key].label,
                                "Concept / formula": fact.formula or f"{fin.taxonomy}:{fact.concept}",
                                "Form": fact.form, "Filed": fact.filed, "Accession": fact.accession,
                                "Derived": "yes" if fact.derived else "", "Revised": "yes" if fact.restated else ""})
        st.dataframe(pd.DataFrame(records), hide_index=True, height=420)
        st.caption("Every value maps to an XBRL concept in a specific filing. When a later filing revises a prior "
                   "year (restatement or recast), the latest filed value is shown and flagged.")
    st.download_button("⬇ All statements, long format with provenance (CSV)",
                       to_csv_bytes(long_format([(ctx.bundle.symbol, ctx.fin)])),
                       file_name=f"{ctx.bundle.symbol}_financials_long.csv", mime="text/csv", key="dl_long")
    freshness_line(ctx)


main()
