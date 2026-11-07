import math

import pytest

from fip.formatting import (MINUS, chart_scale, format_money, format_per_share, format_percent, format_pp,
                            resolve_unit, scale_caption)


@pytest.mark.parametrize("value, scale, expected", [
    (416_161, "M", "$416.16B"),        # 416,161 USD millions -> $416.16B (spec example)
    (1_250_000, "M", "$1.25T"),        # 1,250,000 USD millions -> $1.25T
    (845, "M", "$845.00M"),            # 845 USD millions -> $845M
    (416_161_000_000, "units", "$416.16B"),
    (999, "units", "$999"),
    (1_500, "units", "$1.50K"),
])
def test_money_examples(value, scale, expected):
    assert format_money(value, "USD", input_scale=scale) == expected


def test_money_decimals_zero_for_requirement_style():
    assert format_money(845, "USD", input_scale="M", decimals=0) == "$845M"


def test_dollars_are_never_treated_as_millions():
    # A raw SEC value in dollars must not be inflated by a million.
    assert format_money(416_161_000_000, "USD") == "$416.16B"
    assert format_money(416_161_000_000, "USD") != format_money(416_161_000_000, "USD", input_scale="M")


def test_margin_ratio_to_percent():
    assert format_percent(0.4031) == "40.31%"
    assert format_percent(0.06431, signed=True) == "+6.43%"
    assert format_percent(-0.0272) == f"{MINUS}2.72%"


def test_negative_money_and_currencies():
    assert format_money(-2_722_000_000, "USD") == f"{MINUS}$2.72B"
    assert format_money(-2_722_000_000, "USD", ascii_minus=True) == "-$2.72B"
    assert format_money(48_036_704_000_000, "JPY") == "¥48.04T"
    assert format_money(309_064_000_000, "DKK") == "DKK 309.06B"
    assert format_money(2_894_307_700_000, "TWD") == "NT$2.89T"


def test_fixed_display_unit():
    assert format_money(416_161_000_000, "USD", unit="M") == "$416,161.00M"
    assert format_money(416_161_000_000, "USD", unit="T") == "$0.42T"


def test_missing_values():
    for missing in (None, float("nan"), "abc"):
        assert format_money(missing) == "—"
        assert format_percent(missing) == "—"
    assert format_pp(None) == "—"


def test_percentage_points():
    assert format_pp(0.012) == "+1.2 pp"
    assert format_pp(-0.0345) == f"{MINUS}3.5 pp"
    assert format_pp(0.0) == "0.0 pp"


def test_per_share():
    assert format_per_share(7.46, "USD") == "$7.46"


def test_chart_scale_shared_across_series():
    scale = chart_scale([416e9, 112e9, None, math.nan])
    assert scale.suffix == "B" and scale.divisor == 1e9
    assert scale.axis_title("USD") == "USD billions"
    assert resolve_unit([1.2e12, 5e9]) == "T"
    assert resolve_unit([], "auto") == "units"
    assert scale_caption("USD", "auto", [416e9]) == "USD · billions"
