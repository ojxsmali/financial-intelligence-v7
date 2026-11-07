"""Financial Intelligence Platform V7 — Streamlit entry point.

Run locally:   streamlit run app.py
Desktop:       FinancialIntelligenceV7.exe (see desktop/)
Cloud:         Streamlit Community Cloud, main file = app.py
"""
import logging

import streamlit as st

from fip import APP_NAME

st.set_page_config(page_title=f"{APP_NAME} V7", page_icon="📈", layout="wide",
                   initial_sidebar_state="auto",   # expanded on desktop, collapsed on phones
                   menu_items={"About": "Financial Intelligence Platform V7 — SEC EDGAR fundamentals, rule-based "
                                        "insights and a free-tier Gemini research assistant. Not investment advice."})

from fip.http_client import DataSourceError  # noqa: E402  (after set_page_config)
from fip.ui import components as ui  # noqa: E402
from fip.ui.state import get_universe, init_state, render_sidebar  # noqa: E402
from fip.ui.theme import inject_css  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

inject_css()
try:
    get_universe()
except (DataSourceError, OSError, ValueError):  # explain instead of a blank page; details go to the server log
    logging.getLogger("fip").exception("Universe load failed")
    ui.empty_state("The company universe could not be loaded",
                   "Neither a live listing refresh nor the bundled snapshot was available. Check the network "
                   "connection and that data/universe.csv exists, then reload the page.", "⚠")
    st.stop()
init_state()
render_sidebar()

pages = [
    st.Page("views/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
    st.Page("views/explorer.py", title="Explorer", icon=":material/travel_explore:"),
    st.Page("views/compare.py", title="Compare", icon=":material/compare_arrows:"),
    st.Page("views/statements.py", title="Statements", icon=":material/table_chart:"),
    st.Page("views/insights.py", title="Insights", icon=":material/insights:"),
    st.Page("views/assistant.py", title="AI Research", icon=":material/auto_awesome:"),
    st.Page("views/sources.py", title="Sources", icon=":material/fact_check:"),
]
st.navigation(pages, position="top").run()
ui.footer()
