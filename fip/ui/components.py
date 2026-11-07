"""Reusable, escaped HTML components. Every dynamic string passes through ``esc``."""
from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

from fip import APP_NAME, VERSION
from fip.insights import Insight


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def safe_url(url: str) -> str:
    """Only allow https links to known public sources inside raw HTML."""
    url = str(url or "")
    allowed = ("https://www.sec.gov/", "https://data.sec.gov/", "https://www.nasdaqtrader.com/",
               "https://aistudio.google.com/", "https://ai.google.dev/")
    return esc(url) if url.startswith(allowed) else "#"


def render(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def chip(text: str, kind: str = "", dot: bool = False) -> str:
    dot_html = '<span class="fi-dot"></span>' if dot else ""
    return f'<span class="fi-chip {esc(kind)}">{dot_html}{esc(text)}</span>'


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    sub = f'<div class="fi-sub">{esc(subtitle)}</div>' if subtitle else ""
    render(f'<div class="fi-eyebrow">{esc(eyebrow)}</div><h1 class="fi-title">{esc(title)}</h1>{sub}')


def notice(text: str, kind: str = "") -> None:
    render(f'<div class="fi-notice {esc(kind)}" role="status">{esc(text)}</div>')


def empty_state(title: str, body: str, icon: str = "◇") -> None:
    render(f'<div class="fi-empty"><div style="font-size:1.6rem;color:var(--faint)">{esc(icon)}</div>'
           f'<h3>{esc(title)}</h3><div>{esc(body)}</div></div>')


def skeleton(height: int = 120, count: int = 1) -> str:
    blocks = "".join(f'<div class="fi-skel" style="height:{int(height)}px;margin-bottom:.6rem"></div>'
                     for _ in range(count))
    return blocks


def skeleton_kpis(n: int = 6) -> str:
    cells = "".join('<div class="fi-skel" style="height:104px"></div>' for _ in range(n))
    return f'<div class="fi-kpis" aria-busy="true" aria-label="Loading">{cells}</div>' + skeleton(300)


@dataclass
class Kpi:
    label: str
    value: str
    delta: str = ""
    direction: str = "flat"     # up | down | flat
    foot: str = ""
    tooltip: str = ""
    accent: str = "var(--emerald)"
    available: bool = True


def kpi_grid(items: list[Kpi]) -> None:
    cells = []
    for k in items:
        tip = f'<span class="fi-info" title="{esc(k.tooltip)}" aria-label="{esc(k.tooltip)}">i</span>' if k.tooltip else ""
        delta = f'<span class="fi-delta {esc(k.direction)}">{esc(k.delta)}</span>' if k.delta else "<span></span>"
        cls = "fi-kpi" + ("" if k.available else " na")
        cells.append(
            f'<div class="{cls}" style="--accent:{esc(k.accent)}" role="group" aria-label="{esc(k.label)}">'
            f'<div class="fi-kpi-label"><span>{esc(k.label)}</span>{tip}</div>'
            f'<div class="fi-kpi-value">{esc(k.value)}</div>'
            f'<div class="fi-kpi-foot">{delta}<span>{esc(k.foot)}</span></div></div>'
        )
    render('<div class="fi-kpis">' + "".join(cells) + "</div>")


def company_header(symbol: str, name: str, *, exchange: str, instrument: str, cik, sector: str, sic_desc: str,
                   fye: str, chips: list[str], facts: list[tuple[str, str]]) -> None:
    initials = "".join(w[0] for w in name.split()[:2] if w and w[0].isalnum()).upper()[:2] or symbol[:2]
    fact_html = "".join(f'<div><div class="fi-fact-k">{esc(k)}</div><div class="fi-fact-v">{esc(v)}</div></div>'
                        for k, v in facts)
    meta = [chip(symbol, "sym"), chip(exchange), chip(instrument)]
    if cik:
        meta.append(chip(f"CIK {int(cik)}"))
    if sector and sector != "Unclassified":
        meta.append(chip(sector, "info"))
    meta += chips
    render(
        '<div class="fi-company">'
        f'<div class="fi-company-left"><div class="fi-logo" aria-hidden="true">{esc(initials)}</div>'
        f'<div style="min-width:0"><div class="fi-company-name">{esc(name)}</div>'
        f'<div class="fi-company-meta">{"".join(meta)}</div></div></div>'
        f'<div class="fi-facts">{fact_html}</div></div>'
    )


TONE_COLORS = {"positive": "var(--emerald)", "negative": "var(--rose)", "caution": "var(--amber)",
               "neutral": "var(--cyan)"}
CATEGORY_CHIP = {"Fact": "ok", "Calculation": "info", "Flag": "warn"}


def insight_card(item: Insight) -> None:
    render(
        f'<div class="fi-insight" style="--tone:{TONE_COLORS.get(item.tone, "var(--faint)")}">'
        f'<div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.3rem">'
        f'{chip(item.category, CATEGORY_CHIP.get(item.category, ""))}</div>'
        f'<h4>{esc(item.title)}</h4><p>{esc(item.detail)}</p>'
        f'<div class="fi-rule"><span>Rule: <code>{esc(item.rule)}</code></span><span>Evidence: {esc(item.evidence)}</span></div>'
        '</div>'
    )


def html_table(header: list[str], rows: list[dict]) -> None:
    """rows: {"cells": [...], "cls": "sub|ratio|", "neg": [bool,...]}"""
    head = "".join(f"<th>{esc(h)}</th>" for h in header)
    body = []
    for row in rows:
        tds = []
        for i, cell in enumerate(row["cells"]):
            classes = []
            if cell in ("—", "n/a"):
                classes.append("na")
            if row.get("neg") and i < len(row["neg"]) and row["neg"][i]:
                classes.append("neg")
            text = esc(cell)
            if row.get("marks") and i < len(row["marks"]) and row["marks"][i]:
                text += f'<span class="fi-mark" title="{esc(row["marks"][i])}">●</span>'
            tds.append(f'<td class="{" ".join(classes)}">{text}</td>')
        body.append(f'<tr class="{esc(row.get("cls", ""))}">{"".join(tds)}</tr>')
    render(f'<div class="fi-table-wrap"><table class="fi-table"><thead><tr>{head}</tr></thead>'
           f'<tbody>{"".join(body)}</tbody></table></div>')


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="fi-panel-sub">{esc(subtitle)}</div>' if subtitle else ""
    render(f'<div class="fi-panel-title">{esc(title)}</div>{sub}')


def footer() -> None:
    render(
        f'<div class="fi-footer"><span>{esc(APP_NAME)} v{esc(VERSION)} · Data: SEC EDGAR XBRL, Nasdaq Trader symbol '
        'directory</span><span>Reported annual financial statements — not real-time market data. Educational '
        'research only; not investment advice.</span></div>'
    )
