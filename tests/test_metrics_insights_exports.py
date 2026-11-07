import io
import math

import pandas as pd
import pytest

from conftest import load_fixture
from fip.exports import (CsvImportError, long_format, read_user_csv, sanitize_cell, to_csv_bytes,
                         user_csv_to_financials)
from fip.insights import generate_insights
from fip.metrics import annual_table, cagr, comparison_frame, comparison_warnings, revenue_cagr
from fip.xbrl import extract_financials


def upload(text, scale="M"):
    return user_csv_to_financials(read_user_csv(text.encode(), scale))


def test_growth_and_margins():
    df = annual_table(upload("year,revenue,net_income\n2023,100,12\n2024,115,14\n2025,130,18\n"))
    last = df.iloc[-1]
    assert last["revenue"] == 130e6                                  # millions converted to full units
    assert last["revenue_growth"] == pytest.approx(130 / 115 - 1)
    assert last["net_margin"] == pytest.approx(18 / 130)
    assert last["net_margin_change"] == pytest.approx(18 / 130 - 14 / 115)


def test_growth_not_computed_across_gap():
    df = annual_table(upload("year,revenue,net_income\n2023,100,12\n2025,130,18\n"))
    assert math.isnan(df.iloc[-1]["revenue_growth"])


def test_growth_omitted_from_negative_base():
    df = annual_table(upload("year,revenue,net_income\n2023,100,-5\n2024,110,4\n"))
    assert math.isnan(df.iloc[-1]["net_income_growth"])


def test_margins_undefined_when_revenue_not_positive():
    df = annual_table(upload("year,revenue,net_income\n2024,0,-5\n"))
    assert math.isnan(df.iloc[0]["net_margin"])


def test_cagr():
    assert cagr(100, 121, 2) == pytest.approx(0.10)
    assert math.isnan(cagr(-1, 100, 2))
    fin = extract_financials(load_fixture("AAPL"))
    growth, years = revenue_cagr(annual_table(fin))
    assert years == 5 and -0.5 < growth < 0.5


def test_comparison_warnings_for_currency_and_dates():
    items = [("AAPL", extract_financials(load_fixture("AAPL"))), ("TM", extract_financials(load_fixture("TM"))),
             ("MSFT", extract_financials(load_fixture("MSFT")))]
    frame = comparison_frame(items)
    warnings = " ".join(comparison_warnings(frame))
    assert "currencies" in warnings and "different dates" in warnings and "IFRS" in warnings


def test_insights_flag_non_operating_income_and_bank_operating_income():
    brk = extract_financials(load_fixture("BRK-B"))
    titles = [i.title for i in generate_insights(annual_table(brk), brk.currency)]
    assert "Operating income not reported" in titles
    for item in generate_insights(annual_table(brk), brk.currency):
        assert item.category in {"Fact", "Calculation", "Flag"} and item.rule and item.evidence


def test_insights_empty_data():
    assert generate_insights(pd.DataFrame(), "USD")[0].title == "No annual data"


# ---------------------------------------------------------------- CSV import
def test_csv_import_variants():
    frame = read_user_csv(b"Fiscal Year, Revenue ,Net Income\n2024,\"1,000\",(50)\n", "K")
    assert frame.iloc[0]["revenue"] == 1_000_000 and frame.iloc[0]["net_income"] == -50_000


@pytest.mark.parametrize("payload, message", [
    (b"a,b\n1,2\n", "Missing required"),
    (b"year,revenue,net_income\n2024,1,1\n2024,2,2\n", "Duplicate"),
    (b"year,revenue,net_income\n1800,1,1\n", "between 1900"),
    (b"year,revenue,net_income\nx,y,z\n", "No rows"),
    (b"\xff\xfe\x00bad", "parse"),
])
def test_csv_import_errors(payload, message):
    with pytest.raises(CsvImportError, match=message):
        read_user_csv(payload)


def test_csv_import_size_limit():
    with pytest.raises(CsvImportError, match="1 MB"):
        read_user_csv(b"x" * 1_000_001)


def test_v6_sample_csv_still_supported():
    fin = upload("year,revenue,net_income\n2023,100,12\n2024,115,14\n2025,130,18\n")
    assert len(fin.periods) == 3 and fin.origin == "user upload"


# ---------------------------------------------------------------- CSV export
def test_formula_injection_neutralised():
    assert sanitize_cell("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert sanitize_cell("@SUM(A1)") == "'@SUM(A1)"
    assert sanitize_cell("Apple Inc.") == "Apple Inc."
    assert sanitize_cell(-5.0) == -5.0                      # numbers untouched


def test_long_export_is_valid_csv_with_units_and_provenance():
    fin = extract_financials(load_fixture("AAPL"))
    data = to_csv_bytes(long_format([("AAPL", fin)]))
    assert data.startswith(b"\xef\xbb\xbf")                 # UTF-8 BOM for Excel
    frame = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    row = frame[(frame.metric == "revenue") & (frame.fiscal_year == 2025)].iloc[0]
    assert row["value"] == 416_161_000_000 and row["unit"] == "USD"
    assert "not thousands or millions" in row["scale"]
    assert row["filing_index"].startswith("https://www.sec.gov/Archives/edgar/data/320193/")
    assert {"accession", "form", "filed", "formula_or_concept", "derived"} <= set(frame.columns)
