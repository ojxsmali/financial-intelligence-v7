"""Session state, cached data access and the sidebar shared by every page."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from fip import APP_NAME, VERSION
from fip import config
from fip.data_service import FinancialsResult, load_financials, load_profile
from fip.filings import CompanyProfile
from fip.formatting import DISPLAY_UNIT_LABELS, DISPLAY_UNIT_OPTIONS
from fip.universe import add_search_columns, load_universe
from fip.ui.components import esc, render

DEFAULT_SYMBOL = "AAPL"
DEFAULT_COMPARE = ["AAPL", "MSFT", "GOOGL", "NVDA"]
MAX_COMPARE = 6


# ---------------------------------------------------------------- universe
@dataclass
class Universe:
    frame: pd.DataFrame          # indexed for search
    by_symbol: dict              # symbol -> row dict
    company_symbols: list        # picker options (companies with an SEC CIK)
    meta: dict
    origin: str
    warning: str
    loaded_at: float


@st.cache_resource(ttl=6 * 3600, show_spinner=False)
def get_universe() -> Universe:
    state = load_universe(allow_refresh=True, contact_email=config.sec_contact_email() or None)
    frame = add_search_columns(state.frame)
    records = frame.drop(columns=["_sym", "_key", "_name"]).to_dict("records")
    by_symbol = {r["symbol"]: r for r in records}
    companies = frame[frame["is_company"] & frame["cik"].notna()]
    return Universe(frame=frame, by_symbol=by_symbol, company_symbols=companies["symbol"].tolist(),
                    meta=state.meta, origin=state.origin, warning=state.warning, loaded_at=time.time())


def option_label(universe: Universe, symbol: str) -> str:
    row = universe.by_symbol.get(symbol)
    if not row:
        return symbol
    return f"{symbol} — {row['name']} · {row['exchange']}"


# ---------------------------------------------------------------- company data
@dataclass
class CompanyBundle:
    symbol: str
    entry: dict | None
    result: FinancialsResult | None
    profile: CompanyProfile | None
    profile_error: str = ""

    @property
    def has_financials(self) -> bool:
        return self.result is not None and self.result.ok

    @property
    def display_name(self) -> str:
        if self.entry:
            return self.entry["name"] or self.entry["sec_name"] or self.symbol
        return self.symbol


def _load_bundle(cik: int, contact: str, force: bool) -> tuple[FinancialsResult, CompanyProfile | None, str]:
    result = load_financials(cik, force_refresh=force, contact_email=contact or None)
    profile, err = load_profile(cik, contact_email=contact or None)
    return result, profile, err


@st.cache_data(ttl=1800, show_spinner=False, max_entries=256)
def _cached_bundle(cik: int, contact: str, nonce: int):
    return _load_bundle(cik, contact, force=nonce > 0)


def contact_email() -> str:
    return config.sec_contact_email() or st.session_state.get("sec_contact_session", "")


def company_bundle(symbol: str) -> CompanyBundle:
    universe = get_universe()
    entry = universe.by_symbol.get(symbol)
    if not entry or pd.isna(entry.get("cik")) or not entry.get("is_company"):
        return CompanyBundle(symbol, entry, None, None)
    nonce = st.session_state.get("refresh_nonce", {}).get(int(entry["cik"]), 0)
    result, profile, err = _cached_bundle(int(entry["cik"]), contact_email(), nonce)
    return CompanyBundle(symbol, entry, result, profile, err)


def company_bundles(symbols: list[str]) -> list[CompanyBundle]:
    """Load several companies concurrently (bounded by the shared SEC rate limiter)."""
    universe = get_universe()
    contact = contact_email()
    jobs = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for s in symbols:
            entry = universe.by_symbol.get(s)
            if entry and not pd.isna(entry.get("cik")) and entry.get("is_company"):
                jobs[s] = pool.submit(_load_bundle, int(entry["cik"]), contact, False)
        out = []
        for s in symbols:
            entry = universe.by_symbol.get(s)
            if s in jobs:
                result, profile, err = jobs[s].result()
                out.append(CompanyBundle(s, entry, result, profile, err))
            else:
                out.append(CompanyBundle(s, entry, None, None))
    return out


def request_refresh(cik: int) -> None:
    nonces = st.session_state.setdefault("refresh_nonce", {})
    nonces[int(cik)] = nonces.get(int(cik), 0) + 1


# ---------------------------------------------------------------- session state
def init_state() -> None:
    ss = st.session_state
    if "symbol" not in ss:
        requested = str(st.query_params.get("t", "")).upper().strip()[:12]
        universe = get_universe()
        ss["symbol"] = requested if requested in universe.by_symbol else DEFAULT_SYMBOL
    ss.setdefault("compare", list(DEFAULT_COMPARE))
    ss.setdefault("unit", "auto")
    ss.setdefault("years", 5)


def display_unit() -> str:
    """The segmented control returns None when the active segment is clicked again."""
    return st.session_state.get("unit") or "auto"


def years_shown() -> int:
    return int(st.session_state.get("years") or 5)


def select_company(symbol: str) -> None:
    st.session_state["symbol"] = symbol
    st.query_params["t"] = symbol


def add_to_compare(symbol: str) -> bool:
    lst = st.session_state.setdefault("compare", [])
    if symbol in lst:
        return False
    if len(lst) >= MAX_COMPARE:
        lst.pop(0)
    lst.append(symbol)
    return True


# ---------------------------------------------------------------- sidebar
def _on_pick() -> None:
    st.query_params["t"] = st.session_state["symbol"]


def render_sidebar() -> None:
    universe = get_universe()
    with st.sidebar:
        render(f'<div class="fi-brand"><div class="fi-brand-mark">FI</div><div>'
               f'<div class="fi-brand-name">{esc(APP_NAME)}</div>'
               f'<div class="fi-brand-ver">V{esc(VERSION)} · SEC EDGAR</div></div></div>')

        options = universe.company_symbols
        current = st.session_state["symbol"]
        if current not in options:
            options = [current] + options
        st.selectbox(
            "Company", options, key="symbol", on_change=_on_pick,
            format_func=lambda s: option_label(universe, s), filter_mode="fuzzy",
            help=f"Type a ticker or name. {len(universe.company_symbols):,} listed companies with SEC filings; "
                 "ETFs, funds and other instruments are in Company Explorer.",
        )
        if st.button("＋ Add to comparison", width="stretch", key="sb_add_cmp"):
            if add_to_compare(current):
                st.toast(f"{current} added to comparison")
            else:
                st.toast(f"{current} is already in the comparison")

        st.segmented_control("Display units", DISPLAY_UNIT_OPTIONS[:4], key="unit",
                             format_func=lambda u: {"auto": "Auto", "M": "M", "B": "B", "T": "T"}[u],
                             help="Scale for monetary values. " + ", ".join(
                                 f"{k} = {v}" for k, v in DISPLAY_UNIT_LABELS.items() if k in ("auto", "M", "B", "T")))
        st.select_slider("Fiscal years shown", options=[3, 4, 5, 6, 7, 8, 10], key="years")

        st.divider()
        meta = universe.meta
        rows = [
            ("Listed securities", f"{meta.get('total_securities', len(universe.frame)):,}"),
            ("Companies", f"{meta.get('companies', 0):,}"),
            ("With SEC filer ID", f"{meta.get('with_cik', 0):,}"),
            ("Listings source", universe.origin),
            ("Listings built", str(meta.get("built_at", "—"))[:16].replace("T", " ") + " UTC"),
        ]
        render("".join(f'<div class="fi-status-row"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in rows))
        if universe.warning:
            st.caption(f"⚠ {universe.warning}")

        ai_ok = config.gemini_configured()
        render(f'<div class="fi-status-row"><span>AI assistant</span><b>{"configured" if ai_ok else "off"}</b></div>'
               f'<div class="fi-status-row"><span>SEC contact</span><b>{"set" if contact_email() else "missing"}</b></div>')

        if not config.sec_contact_email():
            with st.expander("Settings · SEC contact", expanded=not contact_email()):
                st.caption("SEC requires automated requests to identify a contact e-mail in the User-Agent. "
                           "It is sent only to sec.gov, kept in this browser session, and never logged.")
                value = st.text_input("Contact e-mail", value=st.session_state.get("sec_contact_session", ""),
                                      placeholder="you@example.com", key="sec_contact_input")
                if value and value != st.session_state.get("sec_contact_session"):
                    if config.is_valid_email(value):
                        st.session_state["sec_contact_session"] = value.strip()
                        st.rerun()
                    else:
                        st.error("Enter a valid e-mail address.")
