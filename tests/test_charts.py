"""Server-rendered chart builders: scales, honesty rules, accessibility hooks and escaping."""
import re

import pandas as pd

from fip.ui import charts
from fip.ui.theme import SERIES


def _df():
    return pd.DataFrame({
        "fiscal_year": [2023, 2024, 2025],
        "period_end": ["2023-09-30", "2024-09-28", "2025-09-27"],
        "revenue": [383.285e9, 391.035e9, 416.161e9],
        "net_income": [96.995e9, 93.736e9, None],
        "loss": [-5e9, 2e9, -1e9],
        "net_margin": [0.253, 0.24, 0.269],
        "gross_margin": [0.44, None, 0.47],
    })


def test_nice_ticks_cover_range_and_include_zero():
    ticks = charts.nice_ticks(12.0, 478.8)
    assert ticks[0] == 0 and ticks[-1] >= 478.8 and 0 in ticks
    steps = {round(b - a, 6) for a, b in zip(ticks, ticks[1:])}
    assert len(steps) == 1 and steps.pop() in (50, 100)
    neg = charts.nice_ticks(-5, 2)
    assert neg[0] <= -5 and neg[-1] >= 2 and 0 in neg


def test_nice_ticks_degenerate_inputs():
    assert charts.nice_ticks(0, 0) == [0, 1] or charts.nice_ticks(0, 0)[-1] > 0
    assert charts.nice_step(0) == 1.0


def test_tick_text_decimals_follow_step():
    assert charts._tick_text(100, 50, "$", "B") == "$100B"
    assert charts._tick_text(0.25, 0.25, "", "%") == "0.25%"
    assert charts._tick_text(-50, 25, "$", "B") == "−$50B"


def test_money_bars_one_scale_exact_values_and_table():
    html = charts.money_bars(_df(), [("revenue", "Revenue"), ("net_income", "Net income")], "USD")
    assert "USD billions" in html                                   # one scale, stated once
    assert "$416.16B" in html                                        # exact formatted value in tooltip/table
    assert html.count('tabindex="0"') == 3                           # one keyboard stop per fiscal year
    assert 'role="img"' in html and "FY2025: Revenue $416.16B; Net income Not reported" in html
    assert "<summary>Data table</summary>" in html and '<th scope="row">FY2024</th>' in html
    assert 'aria-label="Legend"' in html                              # 2 series -> legend present
    assert SERIES[0] in html and SERIES[1] in html                    # fixed slot order


def test_single_series_has_no_legend():
    html = charts.money_bars(_df(), [("revenue", "Revenue")], "USD")
    assert 'aria-label="Legend"' not in html


def test_negative_bars_hang_from_zero():
    html = charts.money_bars(_df(), [("loss", "Result")], "USD")
    assert 'class="fi-bar neg"' in html and 'class="fi-bar pos"' in html
    assert "fi-grid zero" in html
    assert "−$5.00B" in html


def test_ratio_lines_are_straight_and_break_on_missing_values():
    html = charts.ratio_lines(_df(), [("net_margin", "Net"), ("gross_margin", "Gross")])
    assert "polyline" in html and "spline" not in html               # straight segments only
    # gross margin is missing in FY2024, so it contributes no line segment (only isolated points)
    assert html.count("%3Cpolyline") == 1
    assert "n/a" in html                                             # missing value labelled in tooltip/table


def test_empty_series_returns_explanation_not_blank_chart():
    df = _df().assign(revenue=None)
    html = charts.money_bars(df, [("revenue", "Revenue")], "USD")
    assert "fi-chart-empty" in html and "No reported values" in html


def test_comparison_bars_sorted_with_entity_colours_and_missing_note():
    frame = pd.DataFrame({"symbol": ["AAPL", "MSFT", "JPM"], "fiscal_year": [2025, 2025, 2024],
                          "period_end": ["2025-09-27", "2025-06-30", "2024-12-31"],
                          "gross_margin": [0.47, 0.69, None]})
    colors = {"AAPL": SERIES[0], "MSFT": SERIES[1], "JPM": SERIES[2]}
    html = charts.comparison_bars(frame, "gross_margin", "Gross margin", kind="ratio", colors=colors)
    assert html.index("MSFT") < html.index("AAPL")                    # largest first
    assert "69.00%" in html and "47.00%" in html
    assert "Not reported: JPM" in html
    assert re.search(r"background:" + re.escape(SERIES[1]), html)    # MSFT keeps its own colour


def test_trend_comparison_aligns_fiscal_years():
    a = pd.DataFrame({"fiscal_year": [2023, 2024], "revenue": [1e9, 2e9]})
    b = pd.DataFrame({"fiscal_year": [2024, 2025], "revenue": [3e9, 4e9]})
    html = charts.trend_comparison({"AAA": a, "BBB": b}, "revenue", "Revenue", kind="money", currency="USD")
    for fy in ("FY2023", "FY2024", "FY2025"):
        assert f'<th scope="row">{fy}</th>' in html
    assert "AAA $2.00B; BBB $3.00B" in html


def test_labels_are_html_escaped():
    df = _df()
    html = charts.money_bars(df, [("revenue", "<script>x</script>")], "USD")
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_fiscal_year_end_label_is_day_month():
    from fip.filings import CompanyProfile
    assert CompanyProfile(cik=1, name="x", fiscal_year_end="0926").fiscal_year_end_label == "26 Sep"
    assert CompanyProfile(cik=1, name="x", fiscal_year_end="0131").fiscal_year_end_label == "31 Jan"
    assert CompanyProfile(cik=1, name="x", fiscal_year_end="").fiscal_year_end_label == "—"
