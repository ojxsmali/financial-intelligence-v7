"""Server-rendered, accessible charts (HTML + inline SVG) — no client charting library.

Why not Plotly: the old charts were mouse-only, had no text alternative, smoothed lines
between annual points, and shipped ~3.5 MB of JS. These charts:

* use ONE scale per chart, printed in the header ("USD billions");
* draw straight segments between fiscal years (no smoothing — there is no intra-year data);
* have a legend for 2+ series (identity is never colour-alone) and a per-year tooltip that
  opens on hover AND keyboard focus (each fiscal year is one Tab stop);
* always include a "Data table" disclosure with the exact formatted values;
* lay out in CSS percentages, so text stays legible from 320 px to desktop.

Every builder returns an HTML string (pure function, unit-tested); ``show`` renders it.
"""
from __future__ import annotations

import html
import math
from dataclasses import dataclass
from urllib.parse import quote

import pandas as pd

from fip.formatting import chart_scale, currency_symbol, format_money, format_percent, is_missing
from fip.ui.theme import SERIES


def _e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def show(markup: str) -> None:
    import streamlit as st   # local import keeps this module testable without a Streamlit runtime
    st.html(markup)


# ---------------------------------------------------------------- scales
def nice_step(span: float, target: int = 5) -> float:
    if span <= 0 or not math.isfinite(span):
        return 1.0
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def nice_ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    """Round tick values covering [lo, hi] and always including zero."""
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    if lo == hi:
        hi = lo + 1.0
    step = nice_step(hi - lo, target)
    start = math.floor(lo / step + 1e-9) * step
    end = math.ceil(hi / step - 1e-9) * step
    count = int(round((end - start) / step))
    return [round(start + i * step, 10) for i in range(count + 1)]


def _tick_text(value: float, step: float, prefix: str = "", suffix: str = "") -> str:
    decimals = max(0, -math.floor(math.log10(step))) if step > 0 else 0
    while decimals < 4 and abs(round(step, decimals) - step) > 1e-9:
        decimals += 1
    sign = "−" if value < 0 else ""
    return f"{sign}{prefix}{abs(value):,.{decimals}f}{suffix}"


# ---------------------------------------------------------------- shared pieces
@dataclass
class Series:
    label: str
    color: str
    values: list            # plotted numbers in chart units (None = not reported)
    texts: list             # exact formatted values for tooltips and the table


def _legend(series: list[Series], kind: str) -> str:
    if len(series) < 2:
        return ""
    cls = "fi-sw line" if kind == "line" else "fi-sw"
    items = "".join(f'<li><span class="{cls}" style="background:{_e(s.color)}" aria-hidden="true"></span>{_e(s.label)}</li>'
                    for s in series)
    return f'<ul class="fi-legend" aria-label="Legend">{items}</ul>'


def _data_table(title: str, categories: list[str], series: list[Series], first_header: str = "Fiscal year") -> str:
    head = f'<th scope="col">{_e(first_header)}</th>' + "".join(f'<th scope="col">{_e(s.label)}</th>' for s in series)
    rows = []
    for i, cat in enumerate(categories):
        cells = "".join(
            f'<td class="{"na" if s.values[i] is None else ("neg" if s.values[i] < 0 else "")}">{_e(s.texts[i])}</td>'
            for s in series)
        rows.append(f'<tr><th scope="row">{_e(cat)}</th>{cells}</tr>')
    return (f'<details class="fi-datatable"><summary>Data table</summary><div class="fi-table-wrap">'
            f'<table class="fi-table"><caption>{_e(title)}</caption><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details>')


def _figure(title: str, unit_text: str, legend: str, body: str, table: str) -> str:
    head = (f'<div class="fi-fig-head">{legend}<span class="fi-fig-unit">{_e(unit_text)}</span></div>'
            if (legend or unit_text) else "")
    return f'<figure class="fi-fig" aria-label="{_e(title)}">{head}{body}{table}</figure>'


def _empty(message: str) -> str:
    return f'<div class="fi-chart-empty" role="note">{_e(message)}</div>'


def column_chart(categories: list[str], series: list[Series], *, kind: str = "bar", title: str = "",
                 unit_text: str = "", prefix: str = "", suffix: str = "", height: int = 260) -> str:
    """Grouped columns (kind="bar") or straight-segment lines (kind="line") over categories."""
    series = [s for s in series if any(v is not None for v in s.values)]
    if not series or not categories:
        return _empty("No reported values to chart for this selection.")
    values = [v for s in series for v in s.values if v is not None]
    ticks = nice_ticks(min(values), max(values))
    lo, hi = ticks[0], ticks[-1]
    span = hi - lo
    step = ticks[1] - ticks[0] if len(ticks) > 1 else 1.0

    def pct(v: float) -> float:          # distance from the bottom, percent
        return (v - lo) / span * 100

    grid = "".join(
        f'<div class="fi-grid{" zero" if t == 0 else ""}" style="bottom:{pct(t):.3f}%"><span>'
        f'{_e(_tick_text(t, step, prefix, suffix))}</span></div>' for t in ticks)

    n, k = len(categories), len(series)
    col_w = 100 / n
    cols = []
    for i, cat in enumerate(categories):
        marks = []
        if kind == "bar":
            group = 72.0
            bar_w = group / k
            for j, s in enumerate(series):
                v = s.values[i]
                if v is None:
                    continue
                left = (100 - group) / 2 + j * bar_w
                base = pct(min(v, 0.0))          # positive bars sit on zero; negative bars hang from it
                height_pct = abs(v) / span * 100
                marks.append(f'<span class="fi-bar {"neg" if v < 0 else "pos"}" style="left:{left:.3f}%;'
                             f'width:calc({bar_w:.3f}% - 2px);bottom:{base:.3f}%;height:{height_pct:.3f}%;'
                             f'background:{_e(s.color)}"></span>')
        tip_rows = "".join(f'<span><i style="background:{_e(s.color)}"></i>{_e(s.label)}: {_e(s.texts[i])}</span><br>'
                           for s in series)
        aria = f"{cat}: " + "; ".join(f"{s.label} {s.texts[i]}" for s in series)
        cls = "fi-col last" if i == n - 1 and n > 1 else "fi-col"
        cols.append(f'<div class="{cls}" tabindex="0" role="img" aria-label="{_e(aria)}" '
                    f'style="left:{i * col_w:.3f}%;width:{col_w:.3f}%">{"".join(marks)}'
                    f'<span class="x" aria-hidden="true">{_e(cat)}</span>'
                    f'<span class="fi-tip" aria-hidden="true"><b>{_e(cat)}</b>{tip_rows}</span></div>')

    lines = ""
    if kind == "line":
        paths, dots = [], []
        for s in series:
            segment = []
            for i, v in enumerate(s.values):
                x = (i + 0.5) * col_w
                if v is None:
                    if len(segment) > 1:
                        paths.append((s.color, segment))
                    segment = []
                    continue
                segment.append((x, 100 - pct(v)))
                dots.append(f'<span class="fi-pt" style="left:{x:.3f}%;bottom:{pct(v):.3f}%;'
                            f'background:{_e(s.color)}"></span>')
            if len(segment) > 1:
                paths.append((s.color, segment))
        polylines = "".join(
            f'<polyline fill="none" stroke="{_e(c)}" stroke-width="2" stroke-linejoin="round" '
            f'vector-effect="non-scaling-stroke" points="{" ".join(f"{x:.3f},{y:.3f}" for x, y in pts)}"></polyline>'
            for c, pts in paths)
        # Streamlit's HTML sanitizer drops inline <svg> and SVG <img> sources, so the line layer is a CSS background
        # (SVG data URI). It stretches with the plot box (preserveAspectRatio=none) while non-scaling strokes keep
        # lines exactly 2 px wide at any width.
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="none">'
               f'{polylines}</svg>')
        lines = (f'<span class="fi-lines" aria-hidden="true" style="background-image:url(&quot;'
                 f'data:image/svg+xml,{quote(svg, safe="")}&quot;)"></span>{"".join(dots)}')

    body = (f'<div class="fi-chart" style="--h:{int(height)}px">{grid}{lines}{"".join(cols)}</div>')
    return _figure(title, unit_text, _legend(series, kind), body, _data_table(title, categories, series))


def _fy_labels(df: pd.DataFrame) -> list[str]:
    return [f"FY{int(y)}" for y in df["fiscal_year"]]


def _num(v):
    return None if is_missing(v) else float(v)


# ---------------------------------------------------------------- public builders
def money_bars(df: pd.DataFrame, series: list[tuple[str, str]], currency: str, unit: str = "auto",
               title: str = "", height: int = 260) -> str:
    """Grouped bars for monetary series. series = [(column, label), ...] — slots assigned in order."""
    present = [(c, lab) for c, lab in series if c in df and not df[c].isna().all()]
    scale = chart_scale([v for c, _ in present for v in df[c].tolist()], unit)
    sym = currency_symbol(currency).strip()
    built = [Series(lab, SERIES[i % len(SERIES)], [None if _num(v) is None else _num(v) / scale.divisor for v in df[c]],
                    [format_money(v, currency, unit=unit, missing="Not reported") for v in df[c]])
             for i, (c, lab) in enumerate(present)]
    return column_chart(_fy_labels(df), built, kind="bar", title=title or "Annual amounts",
                        unit_text=scale.axis_title(currency), prefix=sym if len(sym) <= 3 else "",
                        suffix=scale.suffix, height=height)


def ratio_lines(df: pd.DataFrame, series: list[tuple[str, str]], title: str = "", height: int = 240) -> str:
    present = [(c, lab) for c, lab in series if c in df and not df[c].isna().all()]
    built = [Series(lab, SERIES[i % len(SERIES)], [None if _num(v) is None else _num(v) * 100 for v in df[c]],
                    [format_percent(v, missing="n/a") for v in df[c]])
             for i, (c, lab) in enumerate(present)]
    return column_chart(_fy_labels(df), built, kind="line", title=title or "Ratios",
                        unit_text="Percent of revenue", suffix="%", height=height)


def comparison_bars(frame: pd.DataFrame, column: str, label: str, *, kind: str, currency: str = "USD",
                    unit: str = "auto", colors: dict | None = None) -> str:
    """Horizontal bars across companies, largest first; every bar carries its exact value."""
    data = frame.dropna(subset=[column]).sort_values(column, ascending=False)
    missing = [s for s in frame["symbol"] if s not in set(data["symbol"])]
    if data.empty:
        return _empty(f"None of the selected companies reports {label.lower()}.")
    colors = colors or {}
    if kind == "ratio":
        values = [float(v) * 100 for v in data[column]]
        texts = [format_percent(v) for v in data[column]]
        unit_text = f"{label}, %"
    else:
        scale = chart_scale(data[column].tolist(), unit)
        values = [float(v) / scale.divisor for v in data[column]]
        texts = [format_money(v, currency, unit=unit) for v in data[column]]
        unit_text = f"{label}, {scale.axis_title(currency)}"
    lo, hi = min(min(values), 0.0), max(max(values), 0.0)
    span = (hi - lo) or 1.0
    zero = (0 - lo) / span * 100
    rows = []
    for (sym, fy), v, t in zip(zip(data["symbol"], data["fiscal_year"]), values, texts):
        left = (min(v, 0) - lo) / span * 100
        width = abs(v) / span * 100
        color = colors.get(sym, SERIES[0])
        rows.append(
            f'<span class="lab">{_e(sym)} <small>FY{int(fy)}</small></span>'
            f'<span class="track" aria-hidden="true"><span class="axis" style="left:{zero:.3f}%"></span>'
            f'<span class="fill" style="left:{left:.3f}%;width:{max(width, 0.4):.3f}%;background:{_e(color)}"></span></span>'
            f'<span class="val{" neg" if v < 0 else ""}">{_e(t)}</span>')
    note = (f'<p class="fi-fig-unit" style="margin:.5rem 0 0">Not reported: {_e(", ".join(missing))}</p>'
            if missing else "")
    body = f'<div class="fi-hbars" role="list" aria-label="{_e(label)}">' + "".join(
        f'<div role="listitem" style="display:contents">{r}</div>' for r in rows) + "</div>" + note
    return _figure(label, unit_text, "", body, "")


def trend_comparison(series_by_symbol: dict[str, pd.DataFrame], column: str, label: str, *, kind: str,
                     currency: str = "USD", unit: str = "auto", height: int = 260, colors: dict | None = None) -> str:
    """Multi-company time series on a shared fiscal-year category axis."""
    colors = colors or {}
    years = sorted({int(y) for df in series_by_symbol.values() for y in df["fiscal_year"]})
    categories = [f"FY{y}" for y in years]
    all_values = [v for df in series_by_symbol.values() for v in df[column].tolist()]
    scale = chart_scale(all_values, unit) if kind == "money" else None
    built = []
    for i, (symbol, df) in enumerate(series_by_symbol.items()):
        if df[column].isna().all():
            continue
        by_year = {int(y): v for y, v in zip(df["fiscal_year"], df[column])}
        raw = [by_year.get(y) for y in years]
        if kind == "ratio":
            vals = [None if _num(v) is None else _num(v) * 100 for v in raw]
            texts = [format_percent(v, missing="—") for v in raw]
        else:
            vals = [None if _num(v) is None else _num(v) / scale.divisor for v in raw]
            texts = [format_money(v, currency, unit=unit) for v in raw]
        built.append(Series(symbol, colors.get(symbol, SERIES[i % len(SERIES)]), vals, texts))
    if kind == "ratio":
        return column_chart(categories, built, kind="line", title=label, unit_text=f"{label}, %", suffix="%",
                            height=height)
    sym = currency_symbol(currency).strip()
    return column_chart(categories, built, kind="line", title=label, unit_text=f"{label}, {scale.axis_title(currency)}",
                        prefix=sym if len(sym) <= 3 else "", suffix=scale.suffix, height=height)
