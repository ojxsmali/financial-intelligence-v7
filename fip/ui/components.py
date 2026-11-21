"""Reusable, escaped HTML components. Every dynamic string passes through ``esc``."""
from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

from fip import APP_NAME, VERSION
from fip.insights import Insight

AUTHOR_NAME = "Ojas Mali"
AUTHOR_URL = "https://github.com/ojxsmali"


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def safe_url(url: str) -> str:
    """Only allow https links to known public sources inside raw HTML."""
    url = str(url or "")
    allowed = ("https://www.sec.gov/", "https://data.sec.gov/", "https://www.nasdaqtrader.com/",
               "https://aistudio.google.com/", "https://ai.google.dev/", AUTHOR_URL)
    return esc(url) if url.startswith(allowed) else "#"


def render(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def chip(text: str, kind: str = "", dot: bool = False) -> str:
    dot_html = '<span class="fi-dot" aria-hidden="true"></span>' if dot else ""
    return f'<span class="fi-chip {esc(kind)}">{dot_html}{esc(text)}</span>'


def tags(items: list[str]) -> None:
    render('<div class="fi-tags">' + "".join(items) + "</div>")


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    sub = f'<p class="fi-sub">{esc(subtitle)}</p>' if subtitle else ""
    render(f'<div class="fi-eyebrow">{esc(eyebrow)}</div><h1 class="fi-title">{esc(title)}</h1>{sub}')


def notice(text: str, kind: str = "") -> None:
    label = {"info": "Note", "bad": "Problem"}.get(kind, "Caveat")
    render(f'<div class="fi-notice {esc(kind)}" role="status"><b>{label}:</b> {esc(text)}</div>')


def empty_state(title: str, body: str, kicker: str = "Nothing to show") -> None:
    render(f'<div class="fi-empty" role="status"><div class="fi-empty-k">{esc(kicker)}</div>'
           f'<h3>{esc(title)}</h3><div class="b">{esc(body)}</div></div>')


def skeleton(height: int = 120, count: int = 1) -> str:
    return "".join(f'<div class="fi-skel" style="height:{int(height)}px;margin-bottom:.6rem"></div>'
                   for _ in range(count))


def skeleton_kpis(n: int = 6, message: str = "Loading annual filings from SEC EDGAR…") -> str:
    cells = "".join('<div class="fi-kpi"><div class="fi-skel" style="height:12px;width:60%"></div>'
                    '<div class="fi-skel" style="height:26px;width:80%;margin-top:.6rem"></div></div>' for _ in range(n))
    return (f'<div role="status" aria-live="polite"><p class="fi-loading">{esc(message)}</p>'
            f'<div class="fi-kpis" aria-hidden="true">{cells}</div>{skeleton(260)}</div>')


@dataclass
class Kpi:
    label: str
    value: str
    delta: str = ""
    direction: str = "flat"     # up | down | flat
    foot: str = ""
    tooltip: str = ""
    accent: str = ""            # kept for API compatibility; KPI tiles are no longer colour-coded
    available: bool = True


_GLYPH = {"up": "▲", "down": "▼", "flat": ""}


def kpi_grid(items: list[Kpi]) -> None:
    cells = []
    for k in items:
        tip = (f'<span class="fi-info" title="{esc(k.tooltip)}" role="img" aria-label="Definition: {esc(k.tooltip)}">i</span>'
               if k.tooltip else "")
        glyph = _GLYPH.get(k.direction, "")
        glyph_html = f'<span aria-hidden="true">{glyph} </span>' if glyph and k.delta else ""
        delta = f'<span class="fi-delta {esc(k.direction)}">{glyph_html}{esc(k.delta)}</span>' if k.delta else ""
        cls = "fi-kpi" + ("" if k.available else " na")
        cells.append(
            f'<div class="{cls}" role="group" aria-label="{esc(k.label)}">'
            f'<div class="fi-kpi-label"><span>{esc(k.label)}</span>{tip}</div>'
            f'<div class="fi-kpi-value">{esc(k.value)}</div>'
            f'<div class="fi-kpi-foot">{delta}<span>{esc(k.foot)}</span></div></div>'
        )
    render('<div class="fi-kpis">' + "".join(cells) + "</div>")


def company_header(symbol: str, name: str, *, exchange: str, instrument: str, cik, sector: str, sic_desc: str,
                   fye: str, chips: list[str], facts: list[tuple[str, str]]) -> None:
    meta = [esc(exchange), esc(instrument)]
    if cik:
        meta.append(f"CIK {int(cik)}")
    if sector and sector != "Unclassified":
        meta.append(esc(sector))
    meta_html = '<span class="sep" aria-hidden="true">/</span>'.join(f"<span>{m}</span>" for m in meta)
    fact_html = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in facts)
    render(
        '<section class="fi-company" aria-label="Company">'
        f'<div class="fi-company-id"><span class="fi-ticker">{esc(symbol)}</span>'
        f'<h2 class="fi-company-name">{esc(name)}</h2>'
        f'<div class="fi-company-meta">{meta_html}</div>'
        f'<div class="fi-tags" style="margin:.6rem 0 0">{"".join(chips)}</div></div>'
        f'<dl class="fi-facts">{fact_html}</dl></section>'
    )


def insight_card(item: Insight) -> None:
    cat_cls = "fi-cat flag" if item.category == "Flag" else "fi-cat"
    render(
        f'<article class="fi-insight"><div class="fi-insight-head"><span class="{cat_cls}">{esc(item.category)}</span>'
        f'<h4>{esc(item.title)}</h4></div><p>{esc(item.detail)}</p>'
        f'<div class="fi-rule"><span>How it&#39;s worked out: {esc(item.how or item.rule)}</span>'
        + (f'<span>Source: {esc(item.source)}</span>' if getattr(item, "source", "") else "")
        + f'<span title="{esc(item.rule)}">Formula <code>{esc(item.rule)}</code></span></div>'
        '</article>'
    )


def html_table(header: list[str], rows: list[dict], caption: str = "") -> None:
    """rows: {"cells": [...], "cls": "sub|ratio|group", "neg": [bool,...], "marks": [str,...]}.
    The first cell of each row is a row header (``<th scope="row">``) for screen readers."""
    head = "".join(f'<th scope="col">{esc(h)}</th>' for h in header)
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
                note = esc(row["marks"][i])
                text += f'<span class="fi-mark" title="{note}" role="img" aria-label="{note}">●</span>'
            tag = 'th scope="row"' if i == 0 else "td"
            close = "th" if i == 0 else "td"
            tds.append(f'<{tag} class="{" ".join(classes)}">{text}</{close}>')
        body.append(f'<tr class="{esc(row.get("cls", ""))}">{"".join(tds)}</tr>')
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    render(f'<div class="fi-table-wrap" role="region" aria-label="{esc(caption or header[0])}" tabindex="0">'
           f'<table class="fi-table">{cap}<thead><tr>{head}</tr></thead>'
           f'<tbody>{"".join(body)}</tbody></table></div>')


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="fi-panel-sub">{esc(subtitle)}</div>' if subtitle else ""
    render(f'<h3 class="fi-panel-title">{esc(title)}</h3>{sub}')


def credit_html() -> str:
    return f'Designed &amp; built by <a href="{AUTHOR_URL}" target="_blank" rel="noopener">{esc(AUTHOR_NAME)}</a>'


def footer() -> None:
    render(
        f'<footer class="fi-footer"><span>{esc(APP_NAME)} v{esc(VERSION)} · Data: SEC EDGAR XBRL, Nasdaq Trader '
        'symbol directory. Reported annual statements — not real-time market data, not investment advice.</span>'
        f'<span>{credit_html()}</span></footer>'
    )
