"""Filings feed, health score, screener and plain-English insights."""
import json

import pandas as pd
import pytest

from conftest import FakeResponse, load_fixture


# ---------------------------------------------------------------- filings feed
SUBMISSIONS = {
    "cik": 320193,
    "filings": {"recent": {
        "form": ["4", "8-K", "10-K", "8-K", "10-Q", "SC 13G", "8-K"],
        "filingDate": ["2026-11-12", "2026-11-09", "2026-11-03", "2026-11-02", "2026-07-31", "2026-02-01", "2026-01-10"],
        "reportDate": ["", "2026-11-09", "2026-09-26", "2026-11-02", "2026-06-27", "", "2026-01-10"],
        "accessionNumber": ["a1", "a2", "a3", "a4", "a5", "a6", "a7"],
        "primaryDocument": ["x.xml", "e.htm", "k.htm", "r.htm", "q.htm", "g.htm", "z.htm"],
        "items": ["", "8.01,9.01", "", "2.02,9.01", "", "", "4.02,9.01"],
    }},
}


def test_events_are_plain_english_sorted_and_hide_noise():
    from fip.events import latest_annual_filing_date, recent_events
    events = recent_events(SUBMISSIONS)
    assert [e.accession for e in events] == ["a2", "a3", "a4", "a5", "a6", "a7"]     # insider Form 4 hidden
    by = {e.accession: e for e in events}
    assert by["a4"].title == "Earnings results released" and by["a4"].importance == "high"
    assert by["a3"].title == "Annual report" and by["a3"].kind == "annual"
    assert by["a7"].importance == "alert" and "no longer be relied on" in by["a7"].title
    assert by["a2"].url.endswith("/a2/e.htm") or "e.htm" in by["a2"].url
    assert latest_annual_filing_date(events) == "2026-11-03"
    assert len(recent_events(SUBMISSIONS, include_noise=True)) == 7


def test_events_tolerate_ragged_columns():
    from fip.events import recent_events
    broken = {"cik": 1, "filings": {"recent": {"form": ["8-K", "10-K"], "filingDate": ["2026-01-01", "2026-02-01"],
                                               "accessionNumber": ["x", "y"], "items": ["2.02"]}}}
    events = recent_events(broken)          # items column shorter than forms -> ignored, not a crash
    assert [e.form for e in events] == ["10-K", "8-K"]


def test_load_events_caches_and_falls_back(monkeypatch):
    from fip import data_service
    calls = []

    def fetcher(url, **kw):
        calls.append(url)
        return FakeResponse(200, SUBMISSIONS)
    events, at, err = data_service.load_events(320193, fetcher=fetcher)
    assert events and at and not err
    data_service.load_events(320193, fetcher=fetcher)
    assert len(calls) == 1                                   # second call served from the hourly cache


# ---------------------------------------------------------------- health score
def _df(**cols):
    base = {"fiscal_year": [2024, 2025], "consecutive": [False, True]}
    base.update(cols)
    return pd.DataFrame(base)


def test_health_all_pass():
    from fip.health import health_score
    df = _df(net_income=[10, 14], total_assets=[100, 105], operating_cash_flow=[12, 18], long_term_debt=[30, 25],
             current_assets=[50, 60], current_liabilities=[40, 40], shares_diluted=[1e9, 0.99e9],
             gross_profit=[40, 45], revenue=[100, 110])
    h = health_score(df)
    assert (h.passed, h.available, h.verdict) == (9, 9, "Strong")
    assert all(c.question.endswith("?") and c.why for c in h.checks)


def test_health_missing_inputs_are_skipped_not_failed():
    from fip.health import health_score
    df = _df(net_income=[10, -5], total_assets=[100, 100], operating_cash_flow=[5, -1], revenue=[100, 90],
             gross_profit=[None, None])
    h = health_score(df)
    skipped = [c.key for c in h.checks if c.passed is None]
    assert {"debt_down", "liquidity_up", "no_dilution", "margin_up"} <= set(skipped)
    # cash (−1) beating profit (−5) still passes the quality test; everything else fails
    assert h.available == 9 - len(skipped) and h.passed == 1 and h.verdict == "Weak"


def test_health_needs_consecutive_years():
    from fip.health import health_score
    df = _df(net_income=[10, 12], total_assets=[100, 100], operating_cash_flow=[5, 15], revenue=[100, 90])
    df.loc[1, "consecutive"] = False
    h = health_score(df)
    assert h.prior_year is None and h.verdict == "Not enough data"
    assert any("previous consecutive" in c.detail for c in h.checks)


def test_health_on_real_filing():
    from fip.health import health_score
    from fip.metrics import annual_table
    from fip.xbrl import extract_financials
    h = health_score(annual_table(extract_financials(load_fixture("AAPL"))))
    assert h.available >= 6 and 0 <= h.passed <= h.available


# ---------------------------------------------------------------- screener
def _frame(rows):
    return FakeResponse(200, {"data": [{"cik": c, "val": v, "accn": "x", "entityName": "n", "end": "2025-12-31"}
                                       for c, v in rows]})


@pytest.fixture()
def frames():
    data = {
        "Revenues/USD/CY2025": [(320193, 400e9), (789019, 280e9), (1, 10e9)],
        "RevenueFromContractWithCustomerExcludingAssessedTax/USD/CY2025": [(320193, 390e9), (1045810, 215e9)],
        "Revenues/USD/CY2024": [(320193, 380e9), (789019, 240e9)],
        "RevenueFromContractWithCustomerExcludingAssessedTax/USD/CY2024": [(1045810, 130e9)],
        "NetIncomeLoss/USD/CY2025": [(320193, 112e9), (789019, 100e9), (1045810, 120e9), (1, 900e9)],
        "Assets/USD/CY2025Q4I": [(320193, 360e9), (789019, 600e9)],
    }

    def fetcher(url, **kw):
        key = url.split("/us-gaap/")[1].removesuffix(".json")
        if key not in data:
            from fip.http_client import NotFoundError
            raise NotFoundError("no frame", status=404)
        return _frame(data[key])
    return fetcher


def test_screener_table_and_ranking(frames):
    from fip import screener
    from fip.api import get_universe
    table = screener.build_table(2025, fetcher=frames)
    apple = table.set_index("cik").loc[320193]
    assert apple["revenue"] == 400e9                                   # largest revenue concept wins
    assert apple["revenue_growth"] == pytest.approx(400 / 380 - 1)
    nvda = table.set_index("cik").loc[1045810]
    assert nvda["revenue_growth"] == pytest.approx(215 / 130 - 1)
    rows, total, excluded = screener.screen(table, get_universe().frame, sort="net_margin")
    assert list(rows["symbol"][:3]) == ["NVDA", "MSFT", "AAPL"] and excluded == 0     # CIK 1 is not listed
    rows, total, _ = screener.screen(table, get_universe().frame, sort="revenue", min_revenue=300e9)
    assert list(rows["symbol"]) == ["AAPL"]


def test_screener_excludes_implausible_ratios(frames):
    from fip import screener
    table = pd.DataFrame([{"cik": 320193, "revenue": 10.0, "net_income": 900.0, "total_assets": 5.0,
                           "net_margin": 90.0, "revenue_growth": None, "return_on_assets": 180.0}])
    from fip.api import get_universe
    rows, total, excluded = screener.screen(table, get_universe().frame, sort="net_margin")
    assert rows.empty and excluded == 1


def test_screener_api_route(client_api, monkeypatch, frames):
    from fip import api, screener
    from fip.data_service import FinancialsResult
    monkeypatch.setattr(screener, "fetch", frames)
    monkeypatch.setattr(api, "load_financials", lambda cik, **kw: FinancialsResult(cik=cik, error="offline"))
    body = client_api.get("/api/screener", params={"year": 2025, "sort": "net_margin", "limit": 2}).json()
    assert body["year"] == 2025 and [r["symbol"] for r in body["rows"]] == ["NVDA", "MSFT"]
    assert body["metrics"]["net_margin"]["kind"] == "ratio"


@pytest.fixture()
def client_api():
    from fastapi.testclient import TestClient
    import fip.api
    fip.api._UNIVERSE = None
    return TestClient(fip.api.app)


def test_symbol_normalisation_and_watchlist(client_api):
    assert client_api.get("/api/company/BRK-B").json()["symbol"] == "BRK.B"
    items = client_api.get("/api/watchlist", params={"symbols": "brk-b,ZZZZ"}).json()["items"]
    assert items[0]["symbol"] == "BRK.B" and items[1]["ok"] is False


def test_validation_errors_use_app_format(client_api):
    body = client_api.get("/api/search", params={"page": 0}).json()
    assert body["error"]["kind"] == "bad_request" and "not valid" in body["error"]["message"]
    assert body["error"]["ref"].startswith("FI-")
    assert client_api.get("/api/no-such-route").json()["error"]["kind"] == "not_found"
    assert client_api.get("/api/symbols", params={"q": ""}).json()["results"] == []


# ---------------------------------------------------------------- plain-English insights
def test_every_insight_has_plain_explanation():
    from fip.insights import generate_insights
    from fip.metrics import annual_table
    from fip.xbrl import extract_financials
    for sym in ("AAPL", "JPM", "TM"):
        fin = extract_financials(load_fixture(sym))
        for item in generate_insights(annual_table(fin), fin.currency, fin.warnings):
            assert item.how, (sym, item.rule)
            assert "_" not in item.how and "/" not in item.how.replace("÷", "")   # no code-style formulas
            assert "filed 20" not in item.source                                    # dates are human-readable


def test_plain_source_formats():
    from fip.insights import plain_source
    assert plain_source("FY2026 10-K filed 2026-11-03") == "FY2026 annual report (10-K), filed 3 Nov 2026"
    assert plain_source("FY2021–FY2026") == "Fiscal years 2021 to 2026"
    assert plain_source("—") == ""


def test_screener_reports_sec_outage_politely(client_api):
    r = client_api.get("/api/screener", params={"year": 2019})        # offline: SEC unreachable, nothing cached
    assert r.status_code == 503 and r.json()["error"]["kind"] == "upstream"



def test_screener_verification_corrects_mistagged_frame_values():
    """SEC frames once reported one quarter of Comfort Systems' revenue as the full year (CY2025)."""
    from fip import screener
    from fip.xbrl import extract_financials
    fin = extract_financials(load_fixture("AAPL"))
    p = next(p for p in fin.periods if p.end.startswith("2024"))
    real_rev = p.values["revenue"].value
    rows = pd.DataFrame([{"cik": fin.cik, "symbol": "AAPL", "name": "Apple", "exchange": "Nasdaq", "sector": "Tech",
                          "revenue": real_rev / 4, "net_income": p.values["net_income"].value, "total_assets": None,
                          "net_margin": 0.9, "revenue_growth": -0.7, "return_on_assets": None}])
    checked = screener.verify_rows(rows, 2024, lambda cik: fin)
    row = checked.iloc[0]
    assert row["verified"] and row["corrected"] and row["revenue"] == real_rev
    assert row["net_margin"] == pytest.approx(p.values["net_income"].value / real_rev)
    unverified = screener.verify_rows(rows, 2024, lambda cik: None).iloc[0]
    assert not unverified["verified"] and unverified["revenue"] == real_rev / 4
    ranked, dropped = screener.finalize(checked, sort="net_margin", descending=True, limit=5)
    assert len(ranked) == 1 and dropped == 0



def test_screener_never_mixes_currencies_when_verifying():
    from fip import screener
    from fip.xbrl import extract_financials
    fin = extract_financials(load_fixture("TM"))             # Toyota reports in JPY
    assert fin.currency != "USD"
    rows = pd.DataFrame([{"cik": fin.cik, "symbol": "TM", "name": "Toyota", "exchange": "NYSE", "sector": "x",
                          "revenue": 300e9, "net_income": 30e9, "total_assets": None, "net_margin": 0.1,
                          "revenue_growth": None, "return_on_assets": None}])
    row = screener.verify_rows(rows, int(fin.latest.end[:4]), lambda cik: fin).iloc[0]
    assert not row["verified"] and row["revenue"] == 300e9          # USD frame value kept, not JPY



def test_meaningful_filings_not_crowded_out_by_routine_ones():
    """JPMorgan files hundreds of 424B2 offering documents; its 8-Ks and 10-Qs must still show."""
    from fip import data_service
    n = 900
    subs = {"cik": 19617, "filings": {"recent": {
        "form": ["424B2"] * n + ["10-Q", "8-K"],
        "filingDate": ["2026-11-20"] * n + ["2026-11-01", "2026-10-15"],
        "accessionNumber": [f"n{i}" for i in range(n)] + ["q", "k"],
        "primaryDocument": ["x"] * (n + 2), "items": [""] * n + ["", "2.02"]}}}
    events, _, err = data_service.load_events(19617, fetcher=lambda url, **kw: FakeResponse(200, subs))
    assert not err and [e.accession for e in events] == ["q", "k"]
