"""Design tokens, global CSS and the Plotly template shared by every page."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

TOKENS = {
    "bg": "#070B14",
    "surface": "#0E1626",
    "surface2": "#111B2E",
    "border": "#1C2940",
    "text": "#E6EDF7",
    "muted": "#8A97AD",
    "faint": "#5B6880",
    "emerald": "#10B981",
    "cyan": "#22D3EE",
    "amber": "#F59E0B",
    "violet": "#A78BFA",
    "rose": "#F43F5E",
    "pink": "#F472B6",
    "blue": "#60A5FA",
}
SERIES = [TOKENS[k] for k in ("emerald", "cyan", "amber", "violet", "pink", "blue")]

CSS = f"""
<style>
:root {{
  --bg:{TOKENS['bg']}; --surface:{TOKENS['surface']}; --surface2:{TOKENS['surface2']};
  --border:{TOKENS['border']}; --text:{TOKENS['text']}; --muted:{TOKENS['muted']}; --faint:{TOKENS['faint']};
  --emerald:{TOKENS['emerald']}; --cyan:{TOKENS['cyan']}; --amber:{TOKENS['amber']};
  --rose:{TOKENS['rose']}; --violet:{TOKENS['violet']};
  --radius:12px; --num: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}}
.stApp {{
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(34,211,238,.07), transparent 60%),
    radial-gradient(900px 420px at -10% 10%, rgba(16,185,129,.06), transparent 55%),
    var(--bg);
}}
.block-container {{ padding-top: 4.2rem; padding-bottom: 3rem; max-width: 1440px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
[data-testid="stHeader"] {{ background: rgba(7,11,20,.78); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border); }}
[data-testid="stSidebar"] {{ border-right: 1px solid var(--border); }}
[data-testid="stCaptionContainer"], .stCaption {{ color: var(--muted) !important; }}
a {{ text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
:focus-visible {{ outline: 2px solid var(--cyan) !important; outline-offset: 2px; }}

/* ---------- page heading ---------- */
.fi-eyebrow {{ font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:var(--emerald);
  font-weight:600; margin-bottom:.15rem; }}
h1.fi-title {{ font-size:1.65rem !important; font-weight:700; color:var(--text); line-height:1.2 !important;
  margin:0; padding:0 !important; }}
.fi-sub {{ color:var(--muted); font-size:.92rem; margin-top:.3rem; }}

/* ---------- company header ---------- */
.fi-company {{ display:flex; flex-wrap:wrap; gap:1rem 1.6rem; align-items:center; justify-content:space-between;
  background:linear-gradient(135deg, rgba(16,185,129,.08), rgba(34,211,238,.04) 45%, rgba(14,22,38,.9));
  border:1px solid var(--border); border-radius:var(--radius); padding:1.1rem 1.3rem; margin:.4rem 0 1rem; }}
.fi-company-name {{ font-size:1.45rem; font-weight:700; color:var(--text); line-height:1.15; }}
.fi-company-meta {{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.5rem; }}
.fi-logo {{ width:46px; height:46px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:1.05rem; color:#04110C; background:linear-gradient(135deg,var(--emerald),var(--cyan));
  flex:0 0 auto; }}
.fi-company-left {{ display:flex; gap:.9rem; align-items:center; min-width:0; }}
.fi-facts {{ display:grid; grid-template-columns:repeat(4, minmax(110px, auto)); gap:.25rem 1.4rem; }}
.fi-fact-k {{ font-size:.68rem; text-transform:uppercase; letter-spacing:.1em; color:var(--faint); }}
.fi-fact-v {{ font-size:.9rem; color:var(--text); font-weight:500; white-space:nowrap; }}

/* ---------- chips ---------- */
.fi-chip {{ display:inline-flex; align-items:center; gap:.35rem; padding:.16rem .55rem; border-radius:999px;
  font-size:.74rem; font-weight:600; border:1px solid var(--border); color:var(--muted); background:rgba(255,255,255,.02);
  white-space:nowrap; }}
.fi-chip.sym {{ color:var(--text); font-family:var(--num); }}
.fi-chip.ok {{ color:var(--emerald); border-color:rgba(16,185,129,.35); background:rgba(16,185,129,.08); }}
.fi-chip.warn {{ color:var(--amber); border-color:rgba(245,158,11,.35); background:rgba(245,158,11,.08); }}
.fi-chip.bad {{ color:var(--rose); border-color:rgba(244,63,94,.35); background:rgba(244,63,94,.08); }}
.fi-chip.info {{ color:var(--cyan); border-color:rgba(34,211,238,.35); background:rgba(34,211,238,.07); }}
.fi-dot {{ width:7px; height:7px; border-radius:50%; background:currentColor; display:inline-block; }}

/* ---------- KPI cards ---------- */
.fi-kpis {{ display:grid; grid-template-columns:repeat(6, minmax(0, 1fr)); gap:.75rem; margin:.2rem 0 1rem; }}
@media (max-width: 1280px) {{ .fi-kpis {{ grid-template-columns:repeat(3, minmax(0, 1fr)); }} }}
.fi-kpi {{ position:relative; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  padding:.9rem 1rem .85rem; transition:border-color .15s ease, transform .15s ease, box-shadow .15s ease; }}
.fi-kpi:hover {{ border-color:rgba(34,211,238,.45); transform:translateY(-1px);
  box-shadow:0 8px 24px rgba(0,0,0,.35); }}
.fi-kpi::before {{ content:""; position:absolute; left:0; top:12px; bottom:12px; width:3px; border-radius:3px;
  background:var(--accent, var(--emerald)); opacity:.9; }}
.fi-kpi-label {{ font-size:.74rem; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-weight:600;
  display:flex; justify-content:space-between; gap:.5rem; }}
.fi-kpi-value {{ font-family:var(--num); font-size:1.55rem; font-weight:600; color:var(--text); margin-top:.3rem;
  font-variant-numeric:tabular-nums; letter-spacing:-.02em; }}
.fi-kpi-foot {{ display:flex; flex-direction:column; align-items:flex-start; gap:.12rem; margin-top:.35rem;
  font-size:.72rem; color:var(--faint); min-height:2.1em; }}
.fi-delta {{ font-family:var(--num); font-weight:600; font-size:.78rem; }}
.fi-delta.up {{ color:var(--emerald); }} .fi-delta.down {{ color:var(--rose); }} .fi-delta.flat {{ color:var(--muted); }}
.fi-kpi.na .fi-kpi-value {{ color:var(--faint); font-size:1.1rem; font-family:inherit; }}
.fi-info {{ cursor:help; color:var(--faint); border:1px solid var(--border); border-radius:50%; width:16px; height:16px;
  display:inline-flex; align-items:center; justify-content:center; font-size:.62rem; text-transform:none; }}

/* ---------- panels / insights ---------- */
.fi-panel-title {{ font-weight:650; font-size:1rem; color:var(--text); margin:.2rem 0 .1rem; }}
.fi-panel-sub {{ color:var(--muted); font-size:.82rem; margin-bottom:.4rem; }}
.fi-insight {{ border:1px solid var(--border); border-radius:var(--radius); padding:.8rem 1rem; margin-bottom:.6rem;
  background:var(--surface); border-left:3px solid var(--tone, var(--faint)); }}
.fi-insight h4 {{ margin:0 0 .25rem; font-size:.98rem; color:var(--text); font-weight:650; }}
.fi-insight p {{ margin:0; color:#C4CFDF; font-size:.88rem; }}
.fi-insight .fi-rule {{ margin-top:.45rem; display:flex; gap:.5rem; flex-wrap:wrap; font-size:.75rem; color:var(--faint); }}
.fi-insight code {{ font-size:.74rem; background:rgba(255,255,255,.04); padding:.05rem .3rem; border-radius:4px; }}

/* ---------- notices ---------- */
.fi-notice {{ border:1px solid rgba(245,158,11,.35); background:rgba(245,158,11,.07); color:#F7D9A6;
  border-radius:10px; padding:.6rem .85rem; font-size:.86rem; margin:.3rem 0 .6rem; }}
.fi-notice.info {{ border-color:rgba(34,211,238,.35); background:rgba(34,211,238,.06); color:#BDEFF7; }}
.fi-notice.bad {{ border-color:rgba(244,63,94,.4); background:rgba(244,63,94,.07); color:#FBC7D1; }}

/* ---------- empty / skeleton ---------- */
.fi-empty {{ text-align:center; border:1px dashed var(--border); border-radius:var(--radius); padding:2.2rem 1rem;
  color:var(--muted); background:rgba(14,22,38,.5); }}
.fi-empty h3 {{ color:var(--text); font-size:1.1rem; margin:.4rem 0; }}
.fi-skel {{ border-radius:var(--radius); background:linear-gradient(90deg, #0E1626 0%, #16223A 50%, #0E1626 100%);
  background-size:200% 100%; animation:fi-shimmer 1.3s ease-in-out infinite; border:1px solid var(--border); }}
@keyframes fi-shimmer {{ 0% {{background-position:200% 0}} 100% {{background-position:-200% 0}} }}
@media (prefers-reduced-motion: reduce) {{ .fi-skel {{ animation:none; }} .fi-kpi {{ transition:none; }} }}

/* ---------- brand (sidebar) ---------- */
.fi-brand {{ display:flex; align-items:center; gap:.6rem; margin:.2rem 0 .8rem; }}
.fi-brand-mark {{ width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,var(--emerald),var(--cyan));
  display:flex; align-items:center; justify-content:center; color:#04110C; font-weight:800; font-size:.95rem; }}
.fi-brand-name {{ font-weight:700; color:var(--text); line-height:1.1; font-size:.98rem; }}
.fi-brand-ver {{ font-size:.7rem; color:var(--faint); letter-spacing:.08em; }}
.fi-status-row {{ display:flex; justify-content:space-between; font-size:.78rem; color:var(--muted); padding:.18rem 0;
  border-bottom:1px dashed rgba(28,41,64,.8); }}
.fi-status-row b {{ color:var(--text); font-weight:600; font-family:var(--num); font-size:.76rem; }}

/* ---------- footer ---------- */
.fi-footer {{ margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--border); color:var(--faint);
  font-size:.78rem; display:flex; flex-wrap:wrap; gap:.4rem 1.2rem; justify-content:space-between; }}

/* ---------- tables ---------- */
.fi-table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
.fi-table th {{ text-align:right; color:var(--muted); font-weight:600; font-size:.74rem; text-transform:uppercase;
  letter-spacing:.06em; padding:.55rem .7rem; border-bottom:1px solid var(--border); background:var(--surface);
  position:sticky; top:0; }}
.fi-table th:first-child, .fi-table td:first-child {{ text-align:left; }}
.fi-table td {{ padding:.5rem .7rem; border-bottom:1px solid rgba(28,41,64,.6); text-align:right;
  font-family:var(--num); font-variant-numeric:tabular-nums; color:var(--text); white-space:nowrap; }}
.fi-table td:first-child {{ font-family:inherit; color:#C4CFDF; }}
.fi-table tr:hover td {{ background:rgba(34,211,238,.035); }}
.fi-table tr.sub td:first-child {{ padding-left:1.4rem; color:var(--muted); }}
.fi-table tr.ratio td {{ color:var(--cyan); }}
.fi-table .na {{ color:var(--faint); }}
.fi-table .neg {{ color:#FDA4AF; }}
.fi-table-wrap {{ overflow-x:auto; border:1px solid var(--border); border-radius:var(--radius); background:rgba(14,22,38,.55); }}
.fi-mark {{ color:var(--amber); font-size:.7rem; vertical-align:super; margin-left:2px; }}

/* ---------- responsive ---------- */
@media (max-width: 900px) {{
  .fi-facts {{ grid-template-columns:repeat(2, minmax(110px, 1fr)); }}
  .fi-kpi-value {{ font-size:1.3rem; }}
  .block-container {{ padding-left:1rem; padding-right:1rem; }}
}}
@media (max-width: 560px) {{
  h1.fi-title {{ font-size:1.3rem !important; }}
  .fi-fact-v {{ white-space:normal; }}
  .fi-logo {{ display:none; }}
  .fi-company-name {{ font-size:1.15rem; }}
  .fi-kpis {{ grid-template-columns:repeat(2, minmax(0, 1fr)); gap:.5rem; }}
  .fi-kpi {{ padding:.7rem .75rem; }}
  .fi-kpi-value {{ font-size:1.1rem; }}
}}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def _register_plotly_template() -> None:
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family="Inter, system-ui, sans-serif", color=TOKENS["text"], size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=SERIES,
        hoverlabel=dict(bgcolor=TOKENS["surface2"], bordercolor=TOKENS["border"],
                        font=dict(family="JetBrains Mono, monospace", size=12, color=TOKENS["text"])),
        xaxis=dict(gridcolor="rgba(28,41,64,.0)", linecolor=TOKENS["border"], tickcolor=TOKENS["border"],
                   tickfont=dict(color=TOKENS["muted"]), title=dict(font=dict(color=TOKENS["muted"], size=11)),
                   zerolinecolor=TOKENS["border"]),
        yaxis=dict(gridcolor="rgba(28,41,64,.75)", linecolor="rgba(0,0,0,0)", tickfont=dict(color=TOKENS["muted"]),
                   title=dict(font=dict(color=TOKENS["muted"], size=11)), zerolinecolor="#2A3A57", zerolinewidth=1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=TOKENS["muted"], size=11), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=8, r=8, t=36, b=8),
        bargap=0.28,
        bargroupgap=0.08,
    )
    pio.templates["fip"] = template
    pio.templates.default = "fip"


_register_plotly_template()
