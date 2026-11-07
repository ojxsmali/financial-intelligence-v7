import math

import pandas as pd
import streamlit as st

from fip.sectors import SECTORS
from fip.ui import components as ui
from fip.ui.state import add_to_compare, get_universe, select_company
from fip.universe import ADR, COMMON, INSTRUMENT_TYPES, search

PAGE_SIZE = 25


def _reset_page() -> None:
    st.session_state["ex_page"] = 1


def main() -> None:
    universe = get_universe()
    frame = universe.frame
    meta = universe.meta
    ui.page_header("Company Explorer", "Search every US-listed security",
                   f"{len(frame):,} securities from Nasdaq, NYSE, NYSE American, NYSE Arca, Cboe BZX and IEX — "
                   f"{int(frame['is_company'].sum()):,} operating companies. Rebuilt daily from official directories.")

    query = st.text_input("Search", key="ex_q", on_change=_reset_page, max_chars=80,
                          placeholder="Ticker or company name — e.g. BRK.B, nvidia, Toyota, JPM",
                          label_visibility="collapsed")
    c1, c2, c3, c4 = st.columns([1.2, 1.4, 1.4, 1], vertical_alignment="bottom")
    exchanges = sorted(frame["exchange"].unique())
    with c1:
        ex = st.multiselect("Exchange", exchanges, key="ex_exch", on_change=_reset_page, placeholder="All exchanges")
    with c2:
        types = st.multiselect("Instrument type", INSTRUMENT_TYPES, default=[COMMON, ADR], key="ex_types",
                               on_change=_reset_page, placeholder="All instrument types",
                               help="Operating companies are 'Common stock' and 'ADR / foreign issuer'. ETFs, funds, "
                                    "warrants, units, rights, preferreds and notes are listed separately.")
    with c3:
        sectors = st.multiselect("Sector (from SEC SIC code)", SECTORS, key="ex_sector", on_change=_reset_page,
                                 placeholder="All sectors")
    with c4:
        filers = st.toggle("SEC filers only", value=True, key="ex_filers", on_change=_reset_page,
                           help="Only securities whose ticker maps to an SEC registrant (CIK).")

    results = search(frame, query, exchanges=ex, types=types, sectors=sectors, only_with_filings=filers)
    total = len(results)
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(st.session_state.get("ex_page", 1), pages)

    chips = [ui.chip(f"{total:,} matches", "info")]
    if query:
        chips.append(ui.chip(f"query: {query}"))
    else:
        results = results.sort_values(["is_company", "symbol"], ascending=[False, True])
    by_ex = results["exchange"].value_counts().head(4)
    chips += [ui.chip(f"{k}: {v:,}") for k, v in by_ex.items()]
    ui.render('<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin:.2rem 0 .6rem">' + "".join(chips) + "</div>")

    if total == 0:
        ui.empty_state("No matching securities",
                       "Try a shorter query, a different spelling, or clear the filters. Tickers are matched with "
                       "or without separators (BRK.B = BRK-B = BRKB).", "⌕")
        return

    view = results.iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    table = pd.DataFrame({
        "Symbol": view["symbol"],
        "Company": view["name"],
        "Exchange": view["exchange"],
        "Type": view["instrument_type"],
        "Sector": view["sector"].replace("Unclassified", "—"),
        "Country": view["country"].replace("", "—"),
        "CIK": view["cik"].astype("Int64").astype(str).replace("<NA>", "—"),
        "Status": view["financial_status"].replace({"": "—", "Normal": "Normal"}),
    })
    event = st.dataframe(
        table, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"ex_table_{page}",
        height=min(38 * len(table) + 40, 38 * PAGE_SIZE + 40),
        column_config={
            "Symbol": st.column_config.TextColumn(width="small"),
            "Company": st.column_config.TextColumn(width="large"),
            "CIK": st.column_config.TextColumn(help="SEC Central Index Key — the registrant whose filings are used"),
            "Status": st.column_config.TextColumn(help="Nasdaq financial status (deficient, delinquent, bankrupt)"),
        },
    )

    nav = st.columns([1, 1, 3, 2.2, 2.2], vertical_alignment="center")
    with nav[0]:
        if st.button("← Prev", disabled=page <= 1, width="stretch", key="ex_prev"):
            st.session_state["ex_page"] = page - 1
            st.rerun()
    with nav[1]:
        if st.button("Next →", disabled=page >= pages, width="stretch", key="ex_next"):
            st.session_state["ex_page"] = page + 1
            st.rerun()
    with nav[2]:
        st.caption(f"Page {page} of {pages:,} · rows {(page - 1) * PAGE_SIZE + 1:,}–{min(page * PAGE_SIZE, total):,}")

    rows = event.selection.rows if event and event.selection else []
    chosen = view.iloc[rows[0]]["symbol"] if rows else None
    with nav[3]:
        # The callback runs before the sidebar picker (key "symbol") is instantiated on the next run.
        if st.button("Open in Overview", type="primary", disabled=chosen is None, width="stretch", key="ex_open",
                     on_click=select_company, args=(chosen,)):
            st.switch_page("views/overview.py")
    with nav[4]:
        if st.button("Add to comparison", disabled=chosen is None, width="stretch", key="ex_cmp"):
            st.toast(f"{chosen} added to comparison" if add_to_compare(chosen) else f"{chosen} already in comparison")
    if chosen is None:
        st.caption("Select a row to open it or add it to the comparison.")

    with st.expander("Universe composition & sources"):
        left, right = st.columns(2)
        with left:
            st.markdown("**By exchange**")
            st.dataframe(frame["exchange"].value_counts().rename_axis("Exchange").reset_index(name="Securities"),
                         hide_index=True)
        with right:
            st.markdown("**By instrument type**")
            st.dataframe(frame["instrument_type"].value_counts().rename_axis("Type").reset_index(name="Securities"),
                         hide_index=True)
        st.caption(
            f"Nasdaq Trader files created {meta.get('nasdaq_file_created', '?')} / {meta.get('other_file_created', '?')}"
            f" (MMDDYYYYHHMM, US Eastern). Universe built {meta.get('built_at', '?')} · origin: {universe.origin}. "
            "Listings missing from today's exchange directories are treated as delisted and excluded."
        )


main()
