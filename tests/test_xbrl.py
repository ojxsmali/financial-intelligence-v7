"""SEC XBRL parsing: synthetic edge cases + regression against real filings (trimmed fixtures)."""
from datetime import date

import pytest

from conftest import load_fixture
from fip.xbrl import CompanyFinancials, NoAnnualDataError, extract_financials


def fact(start, end, val, filed, form="10-K", fy=None, accn=None):
    item = {"end": end, "val": val, "filed": filed, "form": form, "accn": accn or f"0000000000-{filed[2:4]}-{end[5:7]}{end[8:]}"}
    if start:
        item["start"] = start
    if fy is not None:
        item["fy"] = fy
    return item


def companyfacts(concepts, taxonomy="us-gaap", unit="USD", cik=1):
    return {"cik": cik, "entityName": "Test Co", "facts": {taxonomy: {
        name: {"units": {unit: items} if isinstance(items, list) else items} for name, items in concepts.items()}}}


def annual(fy, revenue, ni, end_month_day="-12-31", filed_next=True, accn=None, form="10-K"):
    start = f"{fy}-01-01" if end_month_day == "-12-31" else f"{fy - 1}{end_month_day}"
    end = f"{fy}{end_month_day}"
    filed = f"{fy + 1}-02-15"
    a = accn or f"0000000001-{str(fy + 1)[2:]}-000001"
    return (fact(start, end, revenue, filed, form, fy, a), fact(start, end, ni, filed, form, fy, a))


def test_quarterly_and_ytd_facts_are_excluded():
    r23, n23 = annual(2023, 100e6, 10e6)
    r24, n24 = annual(2024, 120e6, 12e6)
    quarter = fact("2024-10-01", "2024-12-31", 35e6, "2025-02-15", "10-K", 2024, r24["accn"])
    ytd = fact("2024-01-01", "2024-09-30", 85e6, "2024-11-01", "10-Q", 2024)
    fin = extract_financials(companyfacts({"Revenues": [r23, r24, quarter, ytd], "NetIncomeLoss": [n23, n24]}))
    assert [p.fiscal_year for p in fin.periods] == [2023, 2024]
    assert [p.value("revenue") for p in fin.periods] == [100e6, 120e6]


def test_values_are_kept_in_full_units():
    r, n = annual(2024, 416_161_000_000, 112_010_000_000)
    fin = extract_financials(companyfacts({"Revenues": [r], "NetIncomeLoss": [n]}))
    assert fin.latest.value("revenue") == 416_161_000_000


def test_revenue_uses_largest_total_concept_per_period():
    # Insurers/banks report a narrow RevenueFromContract... next to total Revenues.
    r, n = annual(2024, 371e9, 89e9)
    narrow = dict(r, val=247e9)
    fin = extract_financials(companyfacts({"Revenues": [r], "RevenueFromContractWithCustomerExcludingAssessedTax": [narrow],
                                           "NetIncomeLoss": [n]}))
    assert fin.latest.value("revenue") == 371e9
    assert fin.latest.values["revenue"].concept == "Revenues"


def test_concept_switch_over_time_is_stitched():
    r22, n22 = annual(2022, 90e6, 9e6)
    r23, n23 = annual(2023, 100e6, 10e6)
    fin = extract_financials(companyfacts({"SalesRevenueNet": [r22],
                                           "RevenueFromContractWithCustomerExcludingAssessedTax": [r23],
                                           "NetIncomeLoss": [n22, n23]}))
    assert [p.value("revenue") for p in fin.periods] == [90e6, 100e6]


def test_latest_filed_value_wins_and_restatement_is_flagged():
    r23, n23 = annual(2023, 100e6, 10e6)
    r24, n24 = annual(2024, 120e6, 12e6)
    recast = fact(r23["start"], r23["end"], 95e6, "2025-02-15", "10-K", 2024, r24["accn"])
    fin = extract_financials(companyfacts({"Revenues": [r23, r24, recast], "NetIncomeLoss": [n23, n24]}))
    fy23 = fin.periods[0].values["revenue"]
    assert fy23.value == 95e6 and fy23.original_value == 100e6 and fy23.restated
    assert any("revised" in w for w in fin.warnings)


def test_fiscal_year_label_follows_filer_for_january_year_end():
    # Walmart-style year ending 31 Jan 2025 is labelled FY2025 by the filer.
    r = fact("2024-02-01", "2025-01-31", 681e9, "2025-03-14", "10-K", 2025, "0000104169-25-000021")
    n = fact("2024-02-01", "2025-01-31", 19.4e9, "2025-03-14", "10-K", 2025, "0000104169-25-000021")
    fin = extract_financials(companyfacts({"Revenues": [r], "NetIncomeLoss": [n]}))
    assert fin.latest.fiscal_year == 2025


def test_implausible_fy_falls_back_to_end_year():
    r = fact("2024-01-01", "2024-12-31", 1e6, "2025-02-01", "10-K", 2031, "a1")
    n = fact("2024-01-01", "2024-12-31", 1e5, "2025-02-01", "10-K", 2031, "a1")
    fin = extract_financials(companyfacts({"Revenues": [r], "NetIncomeLoss": [n]}))
    assert fin.latest.fiscal_year == 2024


def test_leap_day_year_end_does_not_crash():
    r1 = fact("2023-03-01", "2024-02-29", 10e6, "2024-04-01", "10-K", 2024, "x1")
    n1 = fact("2023-03-01", "2024-02-29", 1e6, "2024-04-01", "10-K", 2024, "x1")
    r2 = fact("2024-03-01", "2025-02-28", 11e6, "2025-04-01", "10-K", 2025, "x2")
    n2 = fact("2024-03-01", "2025-02-28", 1e6, "2025-04-01", "10-K", 2025, "x2")
    fin = extract_financials(companyfacts({"Revenues": [r1, r2], "NetIncomeLoss": [n1, n2]}), today=date(2025, 6, 1))
    assert len(fin.periods) == 2
    assert not any("year-end changed" in w for w in fin.warnings)


def test_fiscal_year_end_change_is_warned():
    r1 = fact("2022-01-01", "2022-12-31", 10e6, "2023-02-01", "10-K", 2022, "y1")
    n1 = fact("2022-01-01", "2022-12-31", 1e6, "2023-02-01", "10-K", 2022, "y1")
    r2 = fact("2023-07-01", "2024-06-30", 12e6, "2024-08-01", "10-K", 2024, "y2")
    n2 = fact("2023-07-01", "2024-06-30", 1e6, "2024-08-01", "10-K", 2024, "y2")
    fin = extract_financials(companyfacts({"Revenues": [r1, r2], "NetIncomeLoss": [n1, n2]}), today=date(2024, 9, 1))
    assert any("year-end changed" in w for w in fin.warnings)


def test_derived_metrics_are_labelled():
    r, n = annual(2024, 100e6, 10e6)
    a = r["accn"]
    concepts = {
        "Revenues": [r], "NetIncomeLoss": [n],
        "CostOfRevenue": [fact(r["start"], r["end"], 60e6, r["filed"], accn=a)],
        "NetCashProvidedByUsedInOperatingActivities": [fact(r["start"], r["end"], 20e6, r["filed"], accn=a)],
        "PaymentsToAcquirePropertyPlantAndEquipment": [fact(r["start"], r["end"], 5e6, r["filed"], accn=a)],
        "LiabilitiesAndStockholdersEquity": [fact(None, r["end"], 200e6, r["filed"], accn=a)],
        "StockholdersEquity": [fact(None, r["end"], 80e6, r["filed"], accn=a)],
    }
    p = extract_financials(companyfacts(concepts)).latest
    assert p.values["gross_profit"].derived and p.value("gross_profit") == 40e6
    assert p.values["free_cash_flow"].derived and p.value("free_cash_flow") == 15e6
    assert p.values["total_liabilities"].derived and p.value("total_liabilities") == 120e6


def test_liabilities_not_derived_when_noncontrolling_interest_exists():
    r, n = annual(2024, 100e6, 10e6)
    a = r["accn"]
    concepts = {"Revenues": [r], "NetIncomeLoss": [n],
                "LiabilitiesAndStockholdersEquity": [fact(None, r["end"], 200e6, r["filed"], accn=a)],
                "StockholdersEquity": [fact(None, r["end"], 80e6, r["filed"], accn=a)],
                "MinorityInterest": [fact(None, r["end"], 5e6, r["filed"], accn=a)]}
    p = extract_financials(companyfacts(concepts)).latest
    assert "total_liabilities" not in p.values   # would be wrong by the NCI amount -> left unavailable


def test_missing_capex_means_no_free_cash_flow():
    r, n = annual(2024, 100e6, 10e6)
    concepts = {"Revenues": [r], "NetIncomeLoss": [n],
                "NetCashProvidedByUsedInOperatingActivities": [fact(r["start"], r["end"], 20e6, r["filed"], accn=r["accn"])]}
    assert "free_cash_flow" not in extract_financials(companyfacts(concepts)).latest.values


def test_only_quarterly_filings_raise_explained_error():
    q = fact("2026-01-01", "2026-03-31", 80e9, "2026-05-01", "10-Q", 2026)
    with pytest.raises(NoAnnualDataError) as err:
        extract_financials(companyfacts({"Revenues": [q], "NetIncomeLoss": [dict(q, val=8e9)]}))
    assert "10-Q" in err.value.user_message


def test_empty_companyfacts():
    with pytest.raises(NoAnnualDataError):
        extract_financials({"cik": 5, "entityName": "Empty", "facts": {}})


def test_reporting_currency_preferred_over_usd_convenience_translation():
    r, n = annual(2024, 2_894e9, 1_158e9)
    r23, n23 = annual(2023, 2_161e9, 851e9)
    usd_r, usd_n = annual(2024, 88e9, 35e9)
    concepts = {"Revenue": {"TWD": [r23, r], "USD": [usd_r]}, "ProfitLossAttributableToOwnersOfParent": {"TWD": [n23, n], "USD": [usd_n]}}
    fin = extract_financials({"cik": 9, "entityName": "TW Co", "facts": {"ifrs-full": {
        k: {"units": v} for k, v in concepts.items()}}})
    assert fin.currency == "TWD" and fin.taxonomy == "ifrs-full"
    assert fin.latest.value("revenue") == 2_894e9


def test_roundtrip_serialization():
    r, n = annual(2024, 100e6, 10e6)
    fin = extract_financials(companyfacts({"Revenues": [r], "NetIncomeLoss": [n]}))
    again = CompanyFinancials.from_dict(fin.to_dict())
    assert again.latest.value("revenue") == 100e6 and again.latest.values["revenue"].concept == "Revenues"


# ---------------------------------------------------------------- real filings
def period(fin, fy):
    return next(p for p in fin.periods if p.fiscal_year == fy)


def test_apple_matches_10k():
    fin = extract_financials(load_fixture("AAPL"))
    fy25 = period(fin, 2025)
    assert fy25.end == "2025-09-27" and fy25.form == "10-K"
    assert fy25.value("revenue") == 416_161_000_000          # Apple FY2025 10-K: net sales $416,161M
    assert fy25.value("net_income") == 112_010_000_000       # net income $112,010M
    assert period(fin, 2024).value("revenue") == 391_035_000_000


def test_microsoft_june_fiscal_year():
    fin = extract_financials(load_fixture("MSFT"))
    fy24 = period(fin, 2024)
    assert fy24.end == "2024-06-30"
    assert fy24.value("revenue") == 245_122_000_000
    assert fy24.value("net_income") == 88_136_000_000


def test_walmart_fiscal_label():
    fin = extract_financials(load_fixture("WMT"))
    fy25 = period(fin, 2025)
    assert fy25.end == "2025-01-31"
    assert round(fy25.value("revenue") / 1e6) == 680_985        # total revenues incl. membership income


def test_berkshire_total_revenue_not_contract_revenue():
    fin = extract_financials(load_fixture("BRK-B"))
    fy24 = period(fin, 2024)
    assert round(fy24.value("revenue") / 1e6) == 371_433
    assert "operating_income" not in fy24.values            # BRK does not report an operating income subtotal


def test_jpmorgan_bank_revenue():
    fin = extract_financials(load_fixture("JPM"))
    fy24 = period(fin, 2024)
    assert round(fy24.value("revenue") / 1e6) == 177_556       # total net revenue
    assert round(fy24.value("net_income") / 1e6) == 58_471
    assert "gross_profit" not in fy24.values


def test_nvidia_fiscal_2025():
    fin = extract_financials(load_fixture("NVDA"))
    fy25 = period(fin, 2025)
    assert fy25.end == "2025-01-26"
    assert fy25.value("revenue") == 130_497_000_000


def test_tsmc_20f_reported_in_twd():
    fin = extract_financials(load_fixture("TSM"))
    assert fin.currency == "TWD" and fin.taxonomy == "ifrs-full" and fin.latest.form == "20-F"
    assert round(period(fin, 2024).value("revenue") / 1e8) == 28_943


def test_toyota_ifrs_not_mixed_with_us_gaap_history():
    fin = extract_financials(load_fixture("TM"))
    assert fin.taxonomy == "ifrs-full" and fin.currency == "JPY"
    assert "US GAAP" in fin.excluded_note
    assert all(p.end >= "2021-03-31" for p in fin.periods)


def test_exxon_holding_company_has_no_annual_data_and_no_substitution():
    with pytest.raises(NoAnnualDataError) as err:
        extract_financials(load_fixture("XOM"))
    assert "10-Q" in err.value.user_message
