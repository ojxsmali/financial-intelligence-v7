import pandas as pd
import streamlit as st

from fip.filings import FORM_DESCRIPTIONS
from fip.gemini import FREE_TIER_MODELS
from fip.metrics import RATIO_DEFINITIONS
from fip.ui import components as ui
from fip.ui.company import load_company_context
from fip.ui.state import get_universe
from fip.universe import NASDAQ_LISTED_URL, OTHER_LISTED_URL, SEC_TICKERS_URL
from fip.xbrl import METRICS, filing_index_url


def _company_sources() -> None:
    ctx = load_company_context()
    if ctx is None:
        return
    fin, profile = ctx.fin, ctx.bundle.profile
    ui.section("Primary data for this company")
    st.markdown(
        f"- **SEC XBRL Company Facts** (all structured financial facts): [{fin.source_url}]({fin.source_url})\n"
        f"- **SEC submissions metadata** (profile, SIC, filing list): "
        f"[data.sec.gov/submissions/CIK{fin.cik:010d}.json](https://data.sec.gov/submissions/CIK{fin.cik:010d}.json)\n"
        + (f"- **EDGAR filing index**: [{profile.name} on EDGAR]({profile.edgar_url})\n" if profile else "")
        + f"- Retrieved: **{fin.retrieved_at[:16].replace('T', ' ')} UTC** · origin: **{fin.origin}** · "
          f"accounting basis: **{'IFRS' if fin.taxonomy == 'ifrs-full' else 'US GAAP'}** · currency: **{fin.currency}**"
    )

    ui.section("Fiscal periods used", "Each row is one annual report; its fiscal year label comes from the filing.")
    rows = []
    for p in reversed(fin.periods):
        doc = None
        if profile:
            doc = next((f for f in profile.annual_filings if f["accession"] == p.accession), None)
        rows.append({
            "Fiscal year": f"FY{p.fiscal_year}", "Period": f"{p.start} → {p.end}", "Form": p.form,
            "Form type": FORM_DESCRIPTIONS.get(p.form, p.form), "Filed": p.filed,
            "Document": doc["url"] if doc else filing_index_url(fin.cik, p.accession),
            "Filing index": filing_index_url(fin.cik, p.accession),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={
        "Document": st.column_config.LinkColumn("Primary document", display_text="Open filing"),
        "Filing index": st.column_config.LinkColumn("Filing index", display_text="Index"),
    })
    if profile and profile.annual_filings:
        with st.expander("All recent annual-report filings on EDGAR"):
            st.dataframe(pd.DataFrame(profile.annual_filings)[["form", "report_date", "filing_date", "accession", "url"]],
                         hide_index=True, column_config={"url": st.column_config.LinkColumn("Document",
                                                                                            display_text="Open")})


def _methodology() -> None:
    ui.section("Metric definitions & XBRL concepts", "Concepts are tried in the order listed (revenue: largest total).")
    rows = []
    for spec in METRICS.values():
        rows.append({"Metric": spec.label, "Statement": spec.statement, "Type": spec.kind,
                     "US GAAP concepts": ", ".join(spec.concepts.get("us-gaap", ())) or "derived",
                     "IFRS concepts": ", ".join(spec.concepts.get("ifrs-full", ())) or "derived",
                     "Notes": spec.description})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    ui.section("Ratio formulas")
    st.dataframe(pd.DataFrame([{"Ratio": label, "Formula": formula} for label, formula in RATIO_DEFINITIONS.values()]),
                 hide_index=True)

    st.markdown("""
**How annual figures are selected**
1. Only facts from annual reports (10-K, 10-K/A, 10-KT, 20-F, 40-F and amendments) are used. Flow items (revenue,
   income, cash flow) must cover 350–380 days, so quarterly and year-to-date values can never leak in.
2. A fiscal year is included only if it is the primary period of an annual report. Its label (FY2026 …) is the
   fiscal year the company itself assigned in that filing — Walmart's year ending 31 Jan 2026 is FY2026.
3. When a later filing revises a prior year (restatement, recast for discontinued operations), the latest filed
   value is shown and marked; the original is kept for reference.
4. One accounting basis (US GAAP or IFRS) and one reporting currency per company. USD convenience translations
   in foreign filings are not used. Amounts are never converted between currencies.
5. Values are stored in full currency units exactly as filed and scaled (K/M/B/T) only for display, with the
   unit printed on every card, axis and table. CSV exports use full units.
6. Growth rates are computed only between consecutive fiscal years and only from a positive base.
7. Missing line items are shown as “—” and explained; nothing is estimated, interpolated or borrowed from
   another registrant.

**Limitations**
- XBRL Company Facts contains only non-dimensional (consolidated) facts: no segment or geographic detail.
- Some recent annual reports appear in EDGAR before their statements reach Company Facts; the app flags this.
- SIC-based sectors are approximate. Listings data reflects exchange directories, not trading activity.
- This platform shows reported financial statements. It does not show stock prices, market capitalisation or
  real-time data, and it does not provide investment advice.
""")


def _platform_sources() -> None:
    universe = get_universe()
    meta = universe.meta
    ui.section("Listing universe")
    st.markdown(
        f"- [Nasdaq Trader — nasdaqlisted.txt]({NASDAQ_LISTED_URL}) · file created {meta.get('nasdaq_file_created', '?')}\n"
        f"- [Nasdaq Trader — otherlisted.txt]({OTHER_LISTED_URL}) (NYSE, NYSE American, NYSE Arca, Cboe BZX, IEX) · "
        f"file created {meta.get('other_file_created', '?')}\n"
        f"- [SEC company_tickers_exchange.json]({SEC_TICKERS_URL}) — ticker → CIK mapping\n"
        f"- SEC submissions metadata — SIC industry, country and fiscal-year end per registrant\n"
        f"- Built **{meta.get('built_at', '?')}**, origin **{universe.origin}**; refreshed automatically every 24 h "
        "(test issues removed; symbols absent from today's exchange directories treated as delisted)."
    )
    ui.section("AI assistant")
    st.markdown(f"Google Gemini API, free-tier models only: `{'`, `'.join(FREE_TIER_MODELS)}` (allowlist verified "
                "against Google's pricing page on 2026-11-03). The model receives only the structured figures shown in "
                "this app.")
    ui.section("SEC fair access")
    st.markdown("Requests identify the operator with a contact e-mail in the User-Agent, are rate-limited to 5 per "
                "second (SEC allows 10), retried with exponential backoff on 429/5xx, and cached (financials 12 h, "
                "profiles 24 h, listings 24 h). See [SEC: Accessing EDGAR data](https://www.sec.gov/os/accessing-edgar-data).")


def main() -> None:
    ui.page_header("Sources & methodology", "Where every number comes from",
                   "Filing links, fiscal periods, XBRL concepts, formulas, timestamps and limitations.")
    t1, t2, t3 = st.tabs(["Selected company", "Methodology", "Platform data sources"])
    with t1:
        _company_sources()
    with t2:
        _methodology()
    with t3:
        _platform_sources()


main()
