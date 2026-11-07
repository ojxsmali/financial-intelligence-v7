"""Map SEC Standard Industrial Classification (SIC) codes to broad sectors.

SEC assigns each registrant a 4-digit SIC code (visible in EDGAR submissions
metadata). SIC predates modern sector schemes such as GICS, so this mapping is a
documented approximation: the raw SIC code and description are always shown next
to the derived sector.
"""
from __future__ import annotations

# (low, high, sector) — first match wins; more specific ranges are listed first.
_RANGES: list[tuple[int, int, str]] = [
    (2830, 2836, "Health Care"),
    (3840, 3851, "Health Care"),
    (5047, 5047, "Health Care"),
    (5122, 5122, "Health Care"),
    (8000, 8099, "Health Care"),
    (8731, 8731, "Health Care"),
    (3570, 3579, "Technology"),
    (3600, 3699, "Technology"),
    (3810, 3829, "Technology"),
    (7370, 7379, "Technology"),
    (4800, 4899, "Communication Services"),
    (2710, 2799, "Communication Services"),
    (7810, 7819, "Communication Services"),
    (7820, 7829, "Communication Services"),
    (1300, 1399, "Energy"),
    (2900, 2999, "Energy"),
    (4610, 4619, "Energy"),
    (4920, 4925, "Energy"),
    (4900, 4991, "Utilities"),
    (6500, 6553, "Real Estate"),
    (6798, 6798, "Real Estate"),
    (6000, 6799, "Financials"),
    (1000, 1099, "Materials"),
    (1400, 1499, "Materials"),
    (2400, 2499, "Materials"),
    (2600, 2699, "Materials"),
    (2800, 2829, "Materials"),
    (2840, 2899, "Materials"),
    (3200, 3399, "Materials"),
    (1500, 1799, "Industrials"),
    (3400, 3569, "Industrials"),
    (3580, 3599, "Industrials"),
    (3700, 3709, "Consumer Discretionary"),
    (3710, 3716, "Consumer Discretionary"),
    (3720, 3799, "Industrials"),
    (3830, 3839, "Industrials"),
    (4000, 4799, "Industrials"),
    (7300, 7369, "Industrials"),
    (7380, 7389, "Industrials"),
    (8700, 8748, "Industrials"),
    (100, 999, "Consumer Staples"),
    (2000, 2199, "Consumer Staples"),
    (5140, 5199, "Consumer Staples"),
    (5400, 5499, "Consumer Staples"),
    (5910, 5912, "Consumer Staples"),
    (2200, 2399, "Consumer Discretionary"),
    (2500, 2599, "Consumer Discretionary"),
    (3000, 3199, "Consumer Discretionary"),
    (3850, 3999, "Consumer Discretionary"),
    (5000, 5139, "Industrials"),
    (5200, 5399, "Consumer Discretionary"),
    (5500, 5909, "Consumer Discretionary"),
    (5913, 5999, "Consumer Discretionary"),
    (7000, 7299, "Consumer Discretionary"),
    (7500, 7999, "Consumer Discretionary"),
    (8200, 8299, "Consumer Discretionary"),
    (6770, 6770, "Shell Companies / SPACs"),
    (9995, 9995, "Shell Companies / SPACs"),
    (8800, 8999, "Other"),
    (9000, 9999, "Other"),
]

# SPAC "blank check" code must win over the generic Financials range.
# Variety / general-merchandise stores (Walmart, Costco) are conventionally Consumer Staples.
_OVERRIDES = {6770: "Shell Companies / SPACs", 6798: "Real Estate", 5331: "Consumer Staples", 5399: "Consumer Staples"}

SECTORS = sorted({s for _, _, s in _RANGES} | {"Unclassified"})


def sector_for_sic(sic) -> str:
    try:
        code = int(str(sic).strip())
    except (TypeError, ValueError):
        return "Unclassified"
    if code in _OVERRIDES:
        return _OVERRIDES[code]
    for low, high, sector in _RANGES:
        if low <= code <= high:
            return sector
    return "Unclassified"
