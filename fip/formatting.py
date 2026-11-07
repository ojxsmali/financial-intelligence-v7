"""One formatting system for every number in the app (cards, tables, charts, exports).

Internally all monetary values are stored in **base currency units** exactly as
SEC reports them (e.g. 416,161,000,000 USD). Scaling to K/M/B/T happens only at
display time, so a value can never be "already in millions" by accident.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MINUS = "−"  # typographic minus for on-screen numbers

SCALES = {
    "units": (1.0, "", "units"),
    "K": (1e3, "K", "thousands"),
    "M": (1e6, "M", "millions"),
    "B": (1e9, "B", "billions"),
    "T": (1e12, "T", "trillions"),
}
DISPLAY_UNIT_OPTIONS = ["auto", "M", "B", "T", "K", "units"]
DISPLAY_UNIT_LABELS = {"auto": "Auto (K/M/B/T)", "K": "Thousands", "M": "Millions", "B": "Billions",
                       "T": "Trillions", "units": "Full units"}

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "CN¥", "TWD": "NT$", "CAD": "C$",
    "AUD": "A$", "HKD": "HK$", "INR": "₹", "KRW": "₩", "BRL": "R$", "MXN": "MX$", "CHF": "CHF ",
    "DKK": "DKK ", "SEK": "SEK ", "NOK": "NOK ", "ILS": "₪", "ZAR": "R ", "SGD": "S$",
}


def is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get((currency or "").upper(), f"{currency} " if currency else "")


def auto_scale(value: float) -> str:
    magnitude = abs(value)
    if magnitude >= 1e12:
        return "T"
    if magnitude >= 1e9:
        return "B"
    if magnitude >= 1e6:
        return "M"
    if magnitude >= 1e3:
        return "K"
    return "units"


def format_money(value, currency: str = "USD", *, unit: str = "auto", decimals: int = 2,
                 input_scale: str = "units", missing: str = "—", ascii_minus: bool = False) -> str:
    """Format a monetary amount.

    ``input_scale`` states the scale the *input* is already in, so a figure
    quoted as 416,161 USD millions is ``format_money(416161, input_scale="M")``
    → ``$416.16B``.
    """
    if is_missing(value):
        return missing
    base = float(value) * SCALES[input_scale][0]
    scale = auto_scale(base) if unit == "auto" else unit
    divisor, suffix, _ = SCALES[scale]
    places = 0 if scale == "units" and float(base).is_integer() else decimals
    body = f"{abs(base) / divisor:,.{places}f}{suffix}"
    sign = ("-" if ascii_minus else MINUS) if base < 0 and round(abs(base) / divisor, places) != 0 else ""
    return f"{sign}{currency_symbol(currency)}{body}"


def format_percent(ratio, *, decimals: int = 2, missing: str = "—", signed: bool = False) -> str:
    """Format a ratio (0.4031) as a percentage ("40.31%")."""
    if is_missing(ratio):
        return missing
    pct = float(ratio) * 100
    text = f"{abs(pct):,.{decimals}f}%"
    if pct < 0 and round(abs(pct), decimals) != 0:
        return MINUS + text
    if signed and round(pct, decimals) > 0:
        return "+" + text
    return text


def format_pp(delta_ratio, *, decimals: int = 1, missing: str = "—") -> str:
    """Change between two ratios, in percentage points (0.012 → "+1.2 pp")."""
    if is_missing(delta_ratio):
        return missing
    pp = float(delta_ratio) * 100
    if round(pp, decimals) == 0:
        return f"0.{''.join('0' for _ in range(decimals))} pp" if decimals else "0 pp"
    return f"{'+' if pp > 0 else MINUS}{abs(pp):,.{decimals}f} pp"


def format_per_share(value, currency: str = "USD", *, missing: str = "—") -> str:
    if is_missing(value):
        return missing
    v = float(value)
    return f"{MINUS if v < 0 else ''}{currency_symbol(currency)}{abs(v):,.2f}"


def format_multiple(value, *, decimals: int = 2, missing: str = "—") -> str:
    if is_missing(value):
        return missing
    return f"{float(value):,.{decimals}f}×"


@dataclass(frozen=True)
class ChartScale:
    divisor: float
    suffix: str
    word: str

    def axis_title(self, currency: str) -> str:
        return f"{currency} {self.word}" if self.word != "units" else currency

    def tick_prefix(self, currency: str) -> str:
        return currency_symbol(currency)


def chart_scale(values, unit: str = "auto") -> ChartScale:
    """Pick one scale for a whole chart so every bar and tooltip shares the axis unit."""
    divisor, suffix, word = SCALES[resolve_unit(values, unit)]
    return ChartScale(divisor, suffix, word)


def resolve_unit(values, unit: str = "auto") -> str:
    """Concrete scale key for a group of values that must share one scale (a table or chart)."""
    if unit != "auto":
        return unit
    finite = [abs(float(v)) for v in values if not is_missing(v)]
    return auto_scale(max(finite)) if finite else "units"


def scale_caption(currency: str, unit: str, values=None) -> str:
    """Human caption such as "USD · billions" for table headers."""
    word = SCALES[resolve_unit(values or [], unit)][2]
    return f"{currency} · {word}" if word != "units" else f"{currency} · full units"
