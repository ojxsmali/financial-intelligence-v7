"""Plotly figures. Every chart uses ONE scale for all series, stated in the axis title,
and hover labels show the exact formatted value with currency, scale and fiscal year."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from fip.formatting import chart_scale, currency_symbol, format_money, format_percent, is_missing
from fip.ui.theme import SERIES, TOKENS

PLOTLY_CONFIG = {"displaylogo": False, "responsive": True,
                 "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
                 "toImageButtonOptions": {"format": "png", "scale": 2}}


def _fy_labels(df: pd.DataFrame) -> list[str]:
    return [f"FY{int(y)}" for y in df["fiscal_year"]]


def money_bars(df: pd.DataFrame, series: list[tuple[str, str]], currency: str, unit: str = "auto",
               title: str = "", height: int = 340) -> go.Figure:
    """Grouped bars for monetary series. series = [(column, label), ...]."""
    values = [v for col, _ in series if col in df for v in df[col].tolist()]
    scale = chart_scale(values, unit)
    sym = currency_symbol(currency).strip()
    fig = go.Figure()
    x = _fy_labels(df)
    for i, (col, label) in enumerate(series):
        if col not in df or df[col].isna().all():
            continue
        y = df[col] / scale.divisor
        hover = [f"{label}<br>{fy}: {format_money(v, currency)}<br><span style='color:{TOKENS['muted']}'>"
                 f"period end {end}</span>" if not is_missing(v) else f"{label}<br>{fy}: not reported"
                 for v, fy, end in zip(df[col], x, df["period_end"])]
        fig.add_bar(x=x, y=y, name=label, marker_color=SERIES[i % len(SERIES)], hovertext=hover,
                    hoverinfo="text", marker_line_width=0, opacity=0.95)
    largest = max([abs(v) / scale.divisor for v in values if not is_missing(v)] or [0])
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TOKENS["text"]), x=0, y=0.98) if title else None,
        height=height, barmode="group", hovermode="closest",
        yaxis=dict(title=dict(text=scale.axis_title(currency)), tickprefix=sym if len(sym) <= 3 else "",
                   ticksuffix=scale.suffix, tickformat=",.0f" if largest >= 10 else ",.1f"),
        xaxis=dict(type="category"),
    )
    return fig


def ratio_lines(df: pd.DataFrame, series: list[tuple[str, str]], title: str = "", height: int = 320) -> go.Figure:
    fig = go.Figure()
    x = _fy_labels(df)
    for i, (col, label) in enumerate(series):
        if col not in df or df[col].isna().all():
            continue
        hover = [f"{label}<br>{fy}: {format_percent(v)}" if not is_missing(v) else f"{label}<br>{fy}: n/a"
                 for v, fy in zip(df[col], x)]
        fig.add_scatter(x=x, y=df[col] * 100, name=label, mode="lines+markers",
                        line=dict(width=2.4, color=SERIES[i % len(SERIES)], shape="spline", smoothing=0.5),
                        marker=dict(size=7, line=dict(width=1.5, color=TOKENS["bg"])),
                        hovertext=hover, hoverinfo="text", connectgaps=False)
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TOKENS["text"]), x=0, y=0.98) if title else None,
        height=height, yaxis=dict(title=dict(text="Percent of revenue"), ticksuffix="%", tickformat=",.0f"),
        xaxis=dict(type="category"),
    )
    return fig


def comparison_bars(frame: pd.DataFrame, column: str, label: str, *, kind: str, currency: str = "USD",
                    unit: str = "auto", height: int = 320) -> go.Figure:
    """Horizontal bars across companies. kind: 'ratio' or 'money' (money requires a single currency)."""
    data = frame.dropna(subset=[column]).sort_values(column)
    fig = go.Figure()
    if data.empty:
        return fig
    labels = [f"{s} · FY{fy}" for s, fy in zip(data["symbol"], data["fiscal_year"])]
    if kind == "ratio":
        x = data[column] * 100
        text = [format_percent(v) for v in data[column]]
        axis = dict(ticksuffix="%", title=dict(text=label + " (%)"))
    else:
        scale = chart_scale(data[column].tolist(), unit)
        x = data[column] / scale.divisor
        text = [format_money(v, currency) for v in data[column]]
        sym = currency_symbol(currency).strip()
        axis = dict(tickprefix=sym if len(sym) <= 3 else "", ticksuffix=scale.suffix,
                    title=dict(text=f"{label} ({scale.axis_title(currency)})"))
    colors = [TOKENS["rose"] if v < 0 else SERIES[i % len(SERIES)] for i, v in enumerate(x)]
    fig.add_bar(x=x, y=labels, orientation="h", marker_color=colors, text=text, textposition="auto",
                hovertext=[f"{lab}<br>{label}: {t}<br>period end {e}" for lab, t, e in
                           zip(labels, text, data["period_end"])], hoverinfo="text",
                textfont=dict(family="JetBrains Mono, monospace", size=11))
    fig.update_layout(height=max(height, 60 * len(data) + 80), xaxis=axis, yaxis=dict(type="category"),
                      showlegend=False, margin=dict(l=8, r=16, t=16, b=8))
    return fig


def trend_comparison(series_by_symbol: dict[str, pd.DataFrame], column: str, label: str, *, kind: str,
                     currency: str = "USD", unit: str = "auto", height: int = 340) -> go.Figure:
    """Multi-company time series (fiscal years on a shared category axis)."""
    fig = go.Figure()
    all_values = [v for df in series_by_symbol.values() for v in df[column].tolist()]
    scale = chart_scale(all_values, unit) if kind == "money" else None
    years = sorted({int(y) for df in series_by_symbol.values() for y in df["fiscal_year"]})
    for i, (symbol, df) in enumerate(series_by_symbol.items()):
        if df[column].isna().all():
            continue
        x = [f"FY{int(y)}" for y in df["fiscal_year"]]
        if kind == "ratio":
            y = df[column] * 100
            hover = [f"{symbol} {fy}: {format_percent(v)}" for v, fy in zip(df[column], x)]
        else:
            y = df[column] / scale.divisor
            hover = [f"{symbol} {fy}: {format_money(v, currency)}" for v, fy in zip(df[column], x)]
        fig.add_scatter(x=x, y=y, name=symbol, mode="lines+markers", hovertext=hover, hoverinfo="text",
                        line=dict(width=2.4, color=SERIES[i % len(SERIES)]), marker=dict(size=7))
    yaxis = (dict(ticksuffix="%", title=dict(text=label + " (%)")) if kind == "ratio" else
             dict(ticksuffix=scale.suffix, title=dict(text=f"{label} ({scale.axis_title(currency)})"),
                  tickprefix=currency_symbol(currency).strip() if len(currency_symbol(currency).strip()) <= 3 else ""))
    fig.update_layout(height=height, yaxis=yaxis,
                      xaxis=dict(type="category", categoryorder="array", categoryarray=[f"FY{y}" for y in years]))
    return fig
