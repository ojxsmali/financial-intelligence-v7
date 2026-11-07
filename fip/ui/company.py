"""Company header + loading/unavailable states shared by the company-centric pages."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from fip.data_service import newer_annual_filing_note
from fip.filings import CompanyProfile
from fip.metrics import annual_table
from fip.ui import components as ui
from fip.ui.state import CompanyBundle, company_bundle, request_refresh, years_shown
from fip.universe import COMPANY_TYPES
from fip.xbrl import CompanyFinancials

ORIGIN_CHIPS = {
    "live": ("Live SEC data", "ok"),
    "disk cache": ("Cached SEC data (<12 h)", "info"),
    "disk cache (stale)": ("Stale cache — refresh failed", "warn"),
    "bundled snapshot": ("Bundled snapshot", "warn"),
}


@dataclass
class CompanyContext:
    bundle: CompanyBundle
    fin: CompanyFinancials
    full: pd.DataFrame     # every available fiscal year
    df: pd.DataFrame       # last N years per the sidebar setting


def _fye_label(bundle: CompanyBundle) -> str:
    if bundle.profile is not None:
        return bundle.profile.fiscal_year_end_label
    # Offline / no SEC contact: fall back to the fiscal year-end stored in the bundled universe.
    fye = str((bundle.entry or {}).get("fiscal_year_end") or "")
    return CompanyProfile(cik=0, name="", fiscal_year_end=fye.zfill(4) if fye.isdigit() else "").fiscal_year_end_label


def load_company_context(show_header: bool = True) -> CompanyContext | None:
    symbol = st.session_state["symbol"]
    placeholder = st.empty()
    placeholder.html(ui.skeleton_kpis())
    bundle = company_bundle(symbol)
    placeholder.empty()

    entry = bundle.entry
    if entry is None:
        ui.empty_state("Symbol not found in current listings",
                       f"{symbol} is not in today's Nasdaq Trader exchange directories. It may have been delisted "
                       "or renamed. Search for the company in Company Explorer.", "⌕")
        return None

    result = bundle.result
    fin = result.financials if result is not None and result.ok else None
    chips = []
    if fin is not None:
        label, kind = ORIGIN_CHIPS.get(fin.origin, (fin.origin, "info"))
        chips.append(ui.chip(label, kind, dot=True))
        chips.append(ui.chip(f"{'IFRS' if fin.taxonomy == 'ifrs-full' else 'US GAAP'} · {fin.currency}"))
    facts = [
        ("Fiscal year-end", _fye_label(bundle)),
        ("Latest annual period", fin.latest.end if fin else "—"),
        ("Annual report", f"{fin.latest.form} · filed {fin.latest.filed}" if fin else "—"),
        ("Industry (SIC)", (bundle.profile.sic_description if bundle.profile else entry.get("sic_description"))
         or "—"),
    ]
    if show_header:
        sector = bundle.profile.sector if bundle.profile else entry.get("sector", "")
        ui.company_header(symbol, bundle.display_name, exchange=entry["exchange"],
                          instrument=entry["instrument_type"], cik=entry.get("cik") if not pd.isna(entry.get("cik"))
                          else None, sector=sector, sic_desc="", fye=_fye_label(bundle), chips=chips, facts=facts)

    # ETFs, funds and trusts can have an SEC CIK too, but they have no operating-company statements.
    if pd.isna(entry.get("cik")) or entry["instrument_type"] not in COMPANY_TYPES:
        if entry["instrument_type"] in COMPANY_TYPES:
            body = ("This listing has no matching SEC registrant in SEC's ticker-to-CIK file (common for banks that "
                    "file with banking regulators instead of the SEC, and for brand-new listings). No financial "
                    "statements are shown rather than borrowing another entity's data.")
        else:
            body = (f"{entry['instrument_type']} securities are not operating companies and do not publish 10-K "
                    "financial statements. Choose a common stock or ADR to see company fundamentals.")
        ui.empty_state("No SEC financial statements for this security", body, "∅")
        return None

    if result is None or not result.ok:
        title = {"no_annual_data": "Annual financial statements unavailable",
                 "not_found": "No structured SEC financial data",
                 "config": "SEC contact e-mail required",
                 "upstream": "SEC data temporarily unavailable"}.get(result.error_kind if result else "",
                                                                      "Financial data unavailable")
        ui.empty_state(title, result.error if result else "Unknown error.", "∅")
        if bundle.profile and bundle.profile.annual_filings:
            st.caption("Annual filings on EDGAR for this registrant:")
            for f in bundle.profile.annual_filings[:3]:
                st.markdown(f"- [{f['form']} filed {f['filing_date']}]({f['url']})")
        elif result is not None and result.error_kind != "config":
            st.markdown(f"[Open this registrant on SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar?action="
                        f"getcompany&CIK={int(entry['cik']):010d})")
        if result is not None and result.error_kind == "upstream" and st.button("Retry SEC request"):
            request_refresh(int(entry["cik"]))
            st.rerun()
        return None

    for message in result.notices:
        ui.notice(message)
    newer = newer_annual_filing_note(fin, bundle.profile)
    if newer:
        ui.notice(newer, "info")
    if fin.excluded_note:
        ui.notice(fin.excluded_note, "info")
    if bundle.profile is None and bundle.profile_error and not result.notices:   # avoid repeating one cause
        st.caption(f"Company profile unavailable: {bundle.profile_error}")

    full = annual_table(fin)
    return CompanyContext(bundle=bundle, fin=fin, full=full, df=full.tail(years_shown()).reset_index(drop=True))


def freshness_line(ctx: CompanyContext) -> None:
    fin = ctx.fin
    cols = st.columns([5, 1.2], vertical_alignment="center")
    with cols[0]:
        st.caption(
            f"Source: SEC XBRL Company Facts for CIK {fin.cik} · retrieved {fin.retrieved_at[:16].replace('T', ' ')} UTC"
            f" · {len(fin.periods)} annual periods available · amounts are reported values in {fin.currency}, "
            "scaled for display only. Not real-time market data."
        )
    with cols[1]:
        if st.button("↻ Re-check SEC", key=f"refresh_{fin.cik}", help="Bypass caches and fetch the latest filing data",
                     width="stretch"):
            request_refresh(fin.cik)
            st.rerun()
