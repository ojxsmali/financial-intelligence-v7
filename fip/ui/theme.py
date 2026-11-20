"""Design tokens and global CSS — the "research paper" design system.

Identity: a printed equity-research note. Warm paper, black ink, one navy accent,
hairline rules instead of boxes, a serif for headings, IBM Plex Sans with tabular
figures for every number. Colour is reserved for data series and for direction
(up/down), and direction is never carried by colour alone (▲ ▼ glyphs + sign).

The chart palette below was checked with a colour-vision-deficiency validator
(OKLab ΔE, protan/deutan/tritan) against the chart surface: all checks pass,
every slot ≥ 3:1 contrast. Series take slots in fixed order — never cycled by rank.
"""
from __future__ import annotations

import streamlit as st

TOKENS = {
    "paper": "#F5F3EE",       # page
    "surface": "#FBFAF7",     # raised surfaces, chart plot area, tables
    "sunken": "#ECE8E0",      # widget fills, skeletons
    "rule": "#D8D3C8",        # hairlines
    "rule_strong": "#16181B", # section rules
    "ink": "#16181B",         # primary text
    "ink2": "#43464C",        # secondary text
    "muted": "#62656B",       # captions (4.9:1 on paper)
    "accent": "#1D3B5A",      # navy ink — links, active nav, primary buttons
    "accent_soft": "#E3E8EE",
    "up": "#1F6A3A",          # positive delta text (with ▲)
    "down": "#A2352A",        # negative delta / negative numbers (with ▼ or −)
    "warn": "#8A5A00",        # caveat text
    "warn_soft": "#F6EDD9",
    "info_soft": "#E6ECF2",
    "bad_soft": "#F5E3DF",
}
# Validated categorical order (light surface #FBFAF7): blue, orange, green, ochre, magenta, violet.
SERIES = ["#1F6FB8", "#D4602C", "#16956A", "#B07A00", "#C2507F", "#6A4FB0"]

# Fonts (IBM Plex Sans / Source Serif 4 / IBM Plex Mono) are loaded by Streamlit from .streamlit/config.toml.
_T = TOKENS
CSS = f"""
<style>
:root {{
  --paper:{_T['paper']}; --surface:{_T['surface']}; --sunken:{_T['sunken']}; --rule:{_T['rule']};
  --rule-strong:{_T['rule_strong']}; --ink:{_T['ink']}; --ink2:{_T['ink2']}; --muted:{_T['muted']};
  --accent:{_T['accent']}; --accent-soft:{_T['accent_soft']}; --up:{_T['up']}; --down:{_T['down']};
  --warn:{_T['warn']}; --warn-soft:{_T['warn_soft']}; --info-soft:{_T['info_soft']}; --bad-soft:{_T['bad_soft']};
  --serif:'Source Serif 4', Georgia, 'Times New Roman', serif;
  --sans:'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --mono:'IBM Plex Mono', ui-monospace, Consolas, monospace;
  --r:4px;
}}

/* ---------- canvas ---------- */
.stApp {{ background:var(--paper); color:var(--ink); }}
.stApp, .stApp button, .stApp input, .stApp textarea {{ font-family:var(--sans); }}
.block-container {{ padding-top:4.6rem; padding-bottom:2rem; max-width:1280px; }}
[data-testid="stHeader"] {{ background:rgba(245,243,238,.94); border-bottom:1px solid var(--rule); }}
[data-testid="stSidebar"] {{ border-right:1px solid var(--rule); }}
[data-testid="stCaptionContainer"], .stCaption {{ color:var(--muted) !important; }}
a {{ color:var(--accent); text-underline-offset:2px; }}
:focus-visible {{ outline:2px solid var(--accent) !important; outline-offset:2px; border-radius:2px; }}
.stApp [data-testid="stMarkdownContainer"] p, .stApp li {{ font-variant-numeric:tabular-nums; }}
h1, h2, h3 {{ font-family:var(--serif) !important; letter-spacing:-.01em; }}

/* ---------- top navigation as a tab rule ---------- */
[data-testid="stHeader"] [data-testid="stTopNavLink"],
[data-testid="stHeader"] a[href] {{ border-radius:0 !important; }}
[data-testid="stTopNavLink"] span {{ font-weight:500; color:var(--ink2); }}
[data-testid="stTopNavLink"][aria-current="page"] {{ box-shadow:inset 0 -2px 0 var(--accent); background:transparent !important; }}
[data-testid="stTopNavLink"][aria-current="page"] span {{ color:var(--ink); font-weight:600; }}

/* ---------- widgets ---------- */
.stButton button, .stDownloadButton button, [data-testid="stPageLink"] a {{ border-radius:var(--r); font-weight:500; }}
.stButton button[kind="primary"]:not(:disabled) {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
.stButton button:disabled {{ background:var(--sunken) !important; border-color:var(--rule) !important;
  color:var(--muted) !important; }}
.stButton button:disabled * {{ color:var(--muted) !important; }}
[data-testid="stButtonGroup"] > div {{ flex-wrap:wrap; }}
[data-testid="stExpander"] details {{ border:1px solid var(--rule); border-radius:var(--r); background:var(--surface); }}
[data-testid="stExpander"] summary p {{ font-weight:500; }}
[data-testid="stTabs"] [role="tab"] p {{ font-weight:500; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:var(--r); }}
[data-testid="stMetricValue"] {{ font-variant-numeric:tabular-nums; }}

/* ---------- page heading ---------- */
.fi-eyebrow {{ font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); font-weight:600; }}
h1.fi-title {{ font-family:var(--serif) !important; font-size:2rem !important; font-weight:600; color:var(--ink);
  line-height:1.15 !important; margin:.2rem 0 0; padding:0 !important; }}
.fi-sub {{ color:var(--ink2); font-size:.95rem; margin:.4rem 0 1.1rem; max-width:62ch; }}

/* ---------- company masthead ---------- */
.fi-company {{ border-top:2px solid var(--rule-strong); border-bottom:1px solid var(--rule); padding:1rem 0 .9rem;
  margin:.2rem 0 1.2rem; display:grid; grid-template-columns:minmax(0,1.3fr) minmax(0,2fr); gap:1rem 2rem; }}
.fi-company-id {{ min-width:0; }}
.fi-ticker {{ font-family:var(--mono); font-size:.8rem; font-weight:500; border:1px solid var(--ink); padding:.05rem .4rem;
  border-radius:2px; color:var(--ink); }}
.fi-company-name {{ font-family:var(--serif); font-size:1.75rem; font-weight:600; line-height:1.15; margin:.45rem 0 .35rem;
  color:var(--ink); overflow-wrap:anywhere; }}
.fi-company-meta {{ font-size:.84rem; color:var(--ink2); display:flex; flex-wrap:wrap; gap:.15rem .5rem; align-items:center; }}
.fi-company-meta .sep {{ color:var(--rule); }}
.fi-facts {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:.8rem 1.4rem; align-content:start; margin:0; }}
.fi-facts div {{ min-width:0; }}
.fi-facts dt {{ font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:600; }}
.fi-facts dd {{ margin:.2rem 0 0; font-size:.92rem; color:var(--ink); font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }}

/* ---------- tags (status / provenance) ---------- */
.fi-chip {{ display:inline-flex; align-items:center; gap:.35rem; font-size:.76rem; font-weight:500; color:var(--ink2);
  padding:.08rem .45rem; border:1px solid var(--rule); border-radius:2px; background:var(--surface); white-space:nowrap; }}
.fi-chip.sym {{ font-family:var(--mono); color:var(--ink); }}
.fi-chip.ok {{ color:var(--up); border-color:#B9D3C1; }}
.fi-chip.warn {{ color:var(--warn); border-color:#E2CB98; background:var(--warn-soft); }}
.fi-chip.bad {{ color:var(--down); border-color:#E3B8B0; background:var(--bad-soft); }}
.fi-chip.info {{ color:var(--accent); border-color:#C3CEDA; }}
.fi-dot {{ width:6px; height:6px; border-radius:50%; background:currentColor; display:inline-block; }}
.fi-tags {{ display:flex; gap:.4rem; flex-wrap:wrap; margin:.2rem 0 .8rem; }}

/* ---------- KPI strip (hairline grid, not cards) ---------- */
.fi-kpis {{ display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule); margin:0 0 1.6rem; }}
.fi-kpi {{ padding:.85rem 1rem .8rem; border-left:1px solid var(--rule); min-width:0; }}
.fi-kpi:first-child {{ border-left:0; padding-left:0; }}
.fi-kpi-label {{ font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-weight:600;
  display:flex; gap:.35rem; align-items:center; }}
.fi-kpi-value {{ font-size:1.6rem; font-weight:500; color:var(--ink); margin-top:.3rem; line-height:1.15;
  font-variant-numeric:tabular-nums lining-nums; letter-spacing:-.015em; white-space:nowrap; }}
.fi-kpi-foot {{ display:flex; flex-direction:column; gap:.1rem; margin-top:.35rem; font-size:.76rem; color:var(--muted);
  font-variant-numeric:tabular-nums; }}
.fi-delta {{ font-weight:600; }}
.fi-delta.up {{ color:var(--up); }} .fi-delta.down {{ color:var(--down); }} .fi-delta.flat {{ color:var(--ink2); }}
.fi-kpi.na .fi-kpi-value {{ color:var(--muted); font-size:1.05rem; font-weight:400; }}
.fi-info {{ cursor:help; color:var(--muted); border:1px solid var(--rule); border-radius:50%; width:15px; height:15px;
  display:inline-flex; align-items:center; justify-content:center; font-size:.6rem; text-transform:none; font-style:italic;
  font-family:var(--serif); }}

/* ---------- sections ---------- */
.fi-panel-title {{ font-family:var(--serif); font-weight:600; font-size:1.15rem; color:var(--ink);
  border-top:1px solid var(--rule-strong); padding-top:.6rem; margin:.4rem 0 .1rem; }}
.fi-panel-sub {{ color:var(--muted); font-size:.82rem; margin-bottom:.6rem; }}

/* ---------- insights (ruled list) ---------- */
.fi-insight {{ border-bottom:1px solid var(--rule); padding:.75rem 0 .8rem; }}
.fi-insight-head {{ display:flex; gap:.5rem; align-items:baseline; flex-wrap:wrap; }}
.fi-insight h4 {{ margin:0; font-size:.98rem; color:var(--ink); font-weight:600; font-family:var(--sans); }}
.fi-cat {{ font-size:.68rem; text-transform:uppercase; letter-spacing:.09em; font-weight:600; color:var(--muted); }}
.fi-cat.flag {{ color:var(--warn); }}
.fi-insight p {{ margin:.25rem 0 0; color:var(--ink2); font-size:.9rem; font-variant-numeric:tabular-nums; }}
.fi-rule {{ margin-top:.4rem; display:flex; gap:.25rem 1rem; flex-wrap:wrap; font-size:.76rem; color:var(--muted); }}
.fi-rule code {{ font-family:var(--mono); font-size:.74rem; background:var(--sunken); padding:.02rem .3rem; border-radius:2px;
  color:var(--ink2); overflow-wrap:anywhere; }}

/* ---------- notices ---------- */
.fi-notice {{ border-left:3px solid var(--warn); background:var(--warn-soft); color:#3D2C05; padding:.55rem .85rem;
  font-size:.88rem; margin:.3rem 0 .7rem; border-radius:0 var(--r) var(--r) 0; }}
.fi-notice b {{ font-weight:600; }}
.fi-notice.info {{ border-left-color:var(--accent); background:var(--info-soft); color:#15283D; }}
.fi-notice.bad {{ border-left-color:var(--down); background:var(--bad-soft); color:#4A160F; }}

/* ---------- empty / loading ---------- */
.fi-empty {{ border:1px solid var(--rule); border-radius:var(--r); padding:2rem 1.4rem; background:var(--surface);
  max-width:640px; margin:1rem 0; }}
.fi-empty .fi-empty-k {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); font-weight:600; }}
.fi-empty h3 {{ font-family:var(--serif) !important; color:var(--ink); font-size:1.25rem; margin:.35rem 0 .4rem; padding:0; }}
.fi-empty div.b {{ color:var(--ink2); font-size:.92rem; }}
.fi-skel {{ background:var(--sunken); border-radius:var(--r); animation:fi-pulse 1.4s ease-in-out infinite; }}
@keyframes fi-pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:.55 }} }}
.fi-loading {{ font-size:.8rem; color:var(--muted); margin:.4rem 0; }}
@media (prefers-reduced-motion: reduce) {{ .fi-skel {{ animation:none; }} }}

/* ---------- sidebar ---------- */
.fi-brand {{ margin:.1rem 0 1rem; }}
.fi-brand-name {{ font-family:var(--serif); font-weight:600; color:var(--ink); line-height:1.1; font-size:1.2rem; }}
.fi-brand-ver {{ font-size:.68rem; color:var(--muted); letter-spacing:.12em; text-transform:uppercase; margin-top:.25rem; }}
.fi-status {{ margin:0; }}
.fi-status-row {{ display:flex; justify-content:space-between; gap:.6rem; font-size:.78rem; color:var(--muted);
  padding:.22rem 0; border-bottom:1px solid var(--rule); }}
.fi-status-row dd {{ margin:0; color:var(--ink); font-weight:500; font-variant-numeric:tabular-nums; text-align:right; }}
.fi-credit {{ font-size:.78rem; color:var(--muted); margin-top:1rem; }}
.fi-credit a {{ color:var(--ink); font-weight:500; }}

/* ---------- footer ---------- */
.fi-footer {{ margin-top:2.8rem; padding-top:.9rem; border-top:1px solid var(--rule); color:var(--muted);
  font-size:.78rem; display:flex; flex-wrap:wrap; gap:.4rem 1.6rem; justify-content:space-between; }}
.fi-footer a {{ color:var(--ink); font-weight:500; }}

/* ---------- tables ---------- */
.fi-table-wrap {{ overflow-x:auto; border-top:1px solid var(--rule-strong); margin:.2rem 0 .4rem; }}
.fi-table {{ width:100%; border-collapse:collapse; font-size:.88rem; font-variant-numeric:tabular-nums lining-nums; }}
.fi-table caption {{ text-align:left; font-size:.78rem; color:var(--muted); padding:.4rem 0; caption-side:bottom; }}
.fi-table th {{ text-align:right; color:var(--muted); font-weight:600; font-size:.72rem; text-transform:uppercase;
  letter-spacing:.06em; padding:.55rem .7rem; border-bottom:1px solid var(--rule); background:var(--paper); white-space:nowrap; }}
.fi-table th:first-child, .fi-table td:first-child, .fi-table th[scope="row"] {{ text-align:left; }}
.fi-table td, .fi-table tbody th {{ padding:.48rem .7rem; border-bottom:1px solid var(--rule); text-align:right;
  color:var(--ink); white-space:nowrap; font-weight:400; }}
.fi-table tbody th {{ color:var(--ink); font-weight:500; text-transform:none; letter-spacing:0; font-size:.88rem; background:none; }}
.fi-table tbody tr:hover td, .fi-table tbody tr:hover th {{ background:var(--surface); }}
.fi-table tr.sub th {{ padding-left:1.5rem; color:var(--ink2); font-weight:400; }}
.fi-table tr.ratio td {{ color:var(--ink2); }}
.fi-table tr.group th {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); font-weight:600;
  padding-top:1rem; }}
.fi-table, .fi-table th, .fi-table td {{ border-left:0 !important; border-right:0 !important; border-top:0 !important; }}
.fi-table .na {{ color:var(--muted); }}
.fi-table .neg {{ color:var(--down); }}
.fi-mark {{ color:var(--warn); font-size:.62rem; vertical-align:super; margin-left:2px; cursor:help; }}

/* ---------- charts (HTML + SVG, responsive, keyboard-inspectable) ---------- */
.fi-fig {{ margin:0 0 .4rem; }}
.fi-fig-head {{ display:flex; justify-content:space-between; gap:.4rem 1rem; flex-wrap:wrap; align-items:baseline; margin-bottom:.5rem; }}
.fi-fig-unit {{ font-size:.76rem; color:var(--muted); }}
.fi-legend {{ display:flex; gap:.3rem 1rem; flex-wrap:wrap; list-style:none; padding:0; margin:0; font-size:.8rem; color:var(--ink2); }}
.fi-legend li {{ display:flex; align-items:center; gap:.4rem; margin:0; }}
.fi-sw {{ width:10px; height:10px; border-radius:2px; display:inline-block; }}
.fi-sw.line {{ height:2px; width:14px; border-radius:1px; }}
.fi-chart {{ position:relative; height:var(--h, 260px); margin-left:56px; margin-bottom:26px; }}
.fi-grid {{ position:absolute; left:0; right:0; border-top:1px solid #E6E2D9; }}
.fi-grid.zero {{ border-top:1px solid #9C9A94; }}
.fi-grid span {{ position:absolute; right:calc(100% + 8px); transform:translateY(-50%); font-size:.72rem; color:var(--muted);
  white-space:nowrap; font-variant-numeric:tabular-nums; }}
.fi-col {{ position:absolute; top:0; bottom:0; outline:none; }}
.fi-col:hover, .fi-col:focus-visible {{ background:rgba(22,24,27,.045); }}
.fi-col:focus-visible {{ box-shadow:inset 0 0 0 2px var(--accent); }}
.fi-col .x {{ position:absolute; top:calc(100% + 6px); left:0; right:0; text-align:center; font-size:.74rem; color:var(--ink2);
  white-space:nowrap; font-variant-numeric:tabular-nums; }}
.fi-bar {{ position:absolute; }}
.fi-bar.pos {{ border-radius:3px 3px 0 0; }}
.fi-bar.neg {{ border-radius:0 0 3px 3px; }}
.fi-lines {{ position:absolute; inset:0; display:block; background-size:100% 100%; background-repeat:no-repeat;
  pointer-events:none; }}
.fi-pt {{ position:absolute; width:8px; height:8px; border-radius:50%; transform:translate(-50%,50%);
  box-shadow:0 0 0 2px var(--surface); pointer-events:none; }}
.fi-tip {{ display:none; position:absolute; z-index:5; bottom:calc(100% - 8px); left:50%; transform:translateX(-50%);
  background:var(--ink); color:#F5F3EE; font-size:.76rem; line-height:1.45; padding:.45rem .6rem; border-radius:3px;
  white-space:nowrap; font-variant-numeric:tabular-nums; pointer-events:none; }}
.fi-tip b {{ font-weight:600; display:block; margin-bottom:.1rem; }}
.fi-tip i {{ display:inline-block; width:8px; height:8px; border-radius:2px; margin-right:.35rem; }}
.fi-col:first-child .fi-tip {{ left:0; transform:none; }}
.fi-col.last .fi-tip {{ left:auto; right:0; transform:none; }}
.fi-col:hover .fi-tip, .fi-col:focus-visible .fi-tip {{ display:block; }}
.fi-hbars {{ display:grid; grid-template-columns:minmax(0,8.5rem) minmax(0,1fr) auto; gap:.45rem .7rem; align-items:center;
  font-size:.82rem; }}
.fi-hbars .lab {{ color:var(--ink); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.fi-hbars .lab small {{ color:var(--muted); font-size:.74rem; }}
.fi-hbars .track {{ position:relative; height:16px; }}
.fi-hbars .track .axis {{ position:absolute; top:-3px; bottom:-3px; border-left:1px solid #9C9A94; }}
.fi-hbars .track .fill {{ position:absolute; top:0; bottom:0; border-radius:2px; }}
.fi-hbars .val {{ text-align:right; font-variant-numeric:tabular-nums; color:var(--ink); white-space:nowrap; }}
.fi-hbars .val.neg {{ color:var(--down); }}
details.fi-datatable {{ margin:.2rem 0 0; font-size:.82rem; }}
details.fi-datatable summary {{ cursor:pointer; color:var(--accent); font-weight:500; width:max-content; }}
details.fi-datatable .fi-table {{ font-size:.82rem; }}
.fi-chart-empty {{ font-size:.85rem; color:var(--muted); padding:1.2rem 0; border-top:1px solid var(--rule); }}

/* ---------- mobile page navigation (Streamlit moves top nav into the drawer on phones) ---------- */
.st-key-fi-mobnav {{ display:none; }}
@media (max-width: 767px) {{
  .st-key-fi-mobnav {{ display:flex; flex-direction:row; flex-wrap:nowrap; overflow-x:auto; gap:.3rem; padding:0 0 .4rem;
    border-bottom:1px solid var(--rule); margin-bottom:.6rem; scrollbar-width:thin; }}
  .st-key-fi-mobnav > div {{ flex:0 0 auto; width:auto !important; }}
  .st-key-fi-mobnav [data-testid="stPageLink"] a {{ padding:.2rem .5rem; }}
}}

/* ---------- responsive ---------- */
@media (max-width: 1180px) {{
  .fi-kpis {{ grid-template-columns:repeat(3, minmax(0,1fr)); }}
  .fi-kpi:nth-child(3n+1) {{ border-left:0; padding-left:0; }}
  .fi-kpi:nth-child(n+4) {{ border-top:1px solid var(--rule); }}
  .fi-company {{ grid-template-columns:1fr; }}
}}
@media (max-width: 767px) {{
  .block-container {{ padding-left:1rem; padding-right:1rem; padding-top:3.6rem; }}
  h1.fi-title {{ font-size:1.5rem !important; }}
  .fi-company-name {{ font-size:1.4rem; }}
  .fi-facts {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
  .fi-kpis {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
  .fi-kpi {{ padding:.7rem .7rem .65rem; }}
  .fi-kpi:nth-child(3n+1) {{ border-left:1px solid var(--rule); padding-left:.7rem; }}
  .fi-kpi:nth-child(2n+1) {{ border-left:0; padding-left:0; }}
  .fi-kpi:nth-child(n+3) {{ border-top:1px solid var(--rule); }}
  .fi-kpi-value {{ font-size:1.25rem; }}
  .fi-chart {{ margin-left:46px; }}
  .fi-col .x {{ font-size:.66rem; }}
  .fi-hbars {{ grid-template-columns:minmax(0,5.5rem) minmax(0,1fr) auto; font-size:.78rem; }}
}}
@media (max-width: 380px) {{
  .fi-kpi-value {{ font-size:1.08rem; }}
  .fi-facts {{ grid-template-columns:1fr; }}
}}
@media (forced-colors: active) {{
  .fi-bar, .fi-hbars .fill, .fi-sw, .fi-pt {{ forced-color-adjust:none; }}
}}
</style>
"""


def inject_css() -> None:
    st.html(CSS)
