"""Financial Intelligence Platform V7 — Streamlit entry point.

Run locally:   streamlit run app.py
Desktop:       FinancialIntelligenceV7.exe (see desktop/)
Cloud:         Streamlit Community Cloud, main file = app.py
"""
import logging

import streamlit as st

from fip import APP_NAME

st.set_page_config(page_title=f"{APP_NAME} V7", page_icon=":material/query_stats:", layout="wide",
                   initial_sidebar_state="auto",   # expanded on desktop, collapsed on phones
                   menu_items={"About": "Financial Intelligence Platform V7 — SEC EDGAR fundamentals, rule-based "
                                        "insights and a free-tier Gemini research assistant. Not investment advice. "
                                        "Designed & built by Ojas Mali — https://github.com/ojxsmali"})

from fip.config import load_dotenv  # noqa: E402  (after set_page_config)
from fip.http_client import DataSourceError  # noqa: E402
from fip.ui import components as ui  # noqa: E402
from fip.ui.state import get_universe, init_state, render_sidebar  # noqa: E402
from fip.ui.theme import inject_css  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

load_dotenv()   # optional local .env (gitignored); real environment variables always win
inject_css()
try:
    get_universe()
except (DataSourceError, OSError, ValueError):  # explain instead of a blank page; details go to the server log
    logging.getLogger("fip").exception("Universe load failed")
    ui.empty_state("The company universe could not be loaded",
                   "Neither a live listing refresh nor the bundled snapshot was available. Check the network "
                   "connection and that data/universe.csv exists, then reload the page.", "Data unavailable")
    st.stop()
init_state()
render_sidebar()

pages = [
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/explorer.py", title="Explorer"),
    st.Page("views/compare.py", title="Compare"),
    st.Page("views/statements.py", title="Statements"),
    st.Page("views/insights.py", title="Insights"),
    st.Page("views/assistant.py", title="Assistant"),
    st.Page("views/sources.py", title="Sources"),
]
nav = st.navigation(pages, position="top")

# On phones Streamlit folds the top navigation into the sidebar drawer; this scrollable row keeps every page
# one tap away. CSS hides it at >= 768 px (display:none also removes it from the accessibility tree there).
with st.container(key="fi-mobnav", horizontal=True, gap="small"):
    for page in pages:
        st.page_link(page)

nav.run()
ui.footer()
