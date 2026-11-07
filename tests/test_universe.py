import json

import pandas as pd
import pytest

from fip.config import BUNDLED_DATA_DIR
from fip.universe import (ADR, COMMON, ETF, PREFERRED, UNIT, WARRANT, add_search_columns, build_universe, classify,
                          read_universe, search, share_classes, symbol_key, to_display_symbol, to_sec_ticker)

NASDAQ = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
GOOG|Alphabet Inc. - Class C Capital Stock|Q|N|N|100|N|N
GOOGL|Alphabet Inc. - Class A Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust, Series 1|G|N|N|100|Y|N
ZXZZT|NASDAQ TEST STOCK|G|Y|N|100|N|N
ABCDW|Abcd Acquisition Corp - Warrant|S|N|N|100|N|N
File Creation Time: 1103202608:46|||||||"""

OTHER = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
BRK.B|Berkshire Hathaway Inc. New Common Stock|N|BRK.B|N|40|N|BRK.B
BRK.A|Berkshire Hathaway Inc. Common Stock|N|BRK.A|N|1|N|BRK.A
JPM|JP Morgan Chase & Co. Common Stock|N|JPM|N|40|N|JPM
BAC$K|Bank of America Corporation Depositary Shares 5.875% Preferred Stock|N|BACpK|N|100|N|BAC-K
TSM|Taiwan Semiconductor Manufacturing Company Ltd.|N|TSM|N|40|N|TSM
SHEL|Shell PLC American Depositary Shares (each representing two (2) Ordinary Shares)|N|SHEL|N|100|N|SHEL
AAC.U|Ares Acquisition Corp Units|N|AAC.U|N|100|N|AAC.U
DDS|Dillard's, Inc. Common Stock|F|DDS|N|40|N|DDS
File Creation Time: 1103202608:46||||||"""

SEC = {"fields": ["cik", "name", "ticker", "exchange"], "data": [
    [320193, "Apple Inc.", "AAPL", "Nasdaq"], [1652044, "Alphabet Inc.", "GOOGL", "Nasdaq"],
    [1652044, "Alphabet Inc.", "GOOG", "Nasdaq"], [1067983, "BERKSHIRE HATHAWAY INC", "BRK-B", "NYSE"],
    [1067983, "BERKSHIRE HATHAWAY INC", "BRK-A", "NYSE"], [19617, "JPMORGAN CHASE & CO", "JPM", "NYSE"],
    [70858, "BANK OF AMERICA CORP /DE/", "BAC-PK", "NYSE"], [1046179, "TAIWAN SEMICONDUCTOR", "TSM", "NYSE"],
    [1306965, "Shell plc", "SHEL", "NYSE"], [28917, "DILLARD'S, INC.", "DDS", "TXSE"],
    [9999999, "Delisted Corp", "GONE", "NYSE"],          # in SEC file but no longer in exchange directories
    [8888888, "Texas Listed Co", "TXCO", "TXSE"],         # exchange not covered by Nasdaq Trader
    [7777777, "OTC Co", "OTCX", "OTC"],
]}


@pytest.fixture(scope="module")
def universe():
    frame, meta = build_universe(NASDAQ, OTHER, SEC)
    return add_search_columns(frame), meta


@pytest.mark.parametrize("symbol, expected", [("BRK.B", "BRK-B"), ("BAC$K", "BAC-PK"), ("AAC.U", "AAC-UN"),
                                              ("AAC.W", "AAC-WT"), ("AIIA.R", "AIIA-RT"), ("AAPL", "AAPL")])
def test_sec_ticker_conversion(symbol, expected):
    assert to_sec_ticker(symbol) == expected


def test_display_and_keys():
    assert to_display_symbol("BRK-B") == "BRK.B"
    assert to_display_symbol("BAC-PK") == "BAC-PK"
    assert symbol_key("brk/b") == symbol_key("BRK-B") == symbol_key("BRK.B") == "BRKB"


@pytest.mark.parametrize("name, etf, symbol, expected", [
    ("Apple Inc. - Common Stock", "N", "AAPL", COMMON),
    ("Invesco QQQ Trust, Series 1", "Y", "QQQ", ETF),
    ("Abcd Acquisition Corp - Warrant", "N", "ABCDW", WARRANT),
    ("Some Corp Units", "N", "AAC.U", UNIT),
    ("Bank Depositary Shares 5.875% Preferred", "N", "BAC$K", PREFERRED),
    ("Shell PLC American Depositary Shares", "N", "SHEL", ADR),
])
def test_classification(name, etf, symbol, expected):
    assert classify(name, etf, symbol) == expected


def test_build_maps_tickers_to_ciks_and_share_classes(universe):
    frame, meta = universe
    rows = frame.set_index("symbol")
    assert rows.loc["BRK.B", "cik"] == 1067983 and rows.loc["BRK.A", "cik"] == 1067983
    assert rows.loc["GOOG", "cik"] == rows.loc["GOOGL", "cik"] == 1652044
    assert rows.loc["BAC$K", "cik"] == 70858 and rows.loc["BAC$K", "instrument_type"] == PREFERRED
    assert not rows.loc["BAC$K", "is_company"]
    assert rows.loc["TSM", "instrument_type"] == COMMON          # no keyword, but SEC maps the exact ticker
    assert sorted(share_classes(frame, 1067983)) == ["BRK.A", "BRK.B"]
    assert meta["total_securities"] == len(frame)


def test_test_issues_delistings_and_otc_are_excluded(universe):
    frame, _ = universe
    symbols = set(frame["symbol"])
    assert "ZXZZT" not in symbols       # Nasdaq test issue
    assert "GONE" not in symbols        # SEC-only NYSE ticker -> treated as delisted
    assert "OTCX" not in symbols        # OTC is not an exchange listing
    assert "TXCO" in symbols            # Texas Stock Exchange listing kept from SEC file


def test_undocumented_exchange_code_uses_sec_label(universe):
    frame, _ = universe
    assert frame.set_index("symbol").loc["DDS", "exchange"] == "Texas Stock Exchange"


def test_search_ranking(universe):
    frame, _ = universe
    assert search(frame, "brk b").iloc[0]["symbol"] == "BRK.B"
    assert search(frame, "BRK-A").iloc[0]["symbol"] == "BRK.A"
    assert search(frame, "goog").iloc[0]["symbol"] == "GOOG"
    assert set(search(frame, "alphabet")["symbol"]) == {"GOOG", "GOOGL"}
    assert search(frame, "apple").iloc[0]["symbol"] == "AAPL"
    assert search(frame, "zzzz-no-match").empty
    assert search(frame, "(").empty     # regex metacharacters are escaped


def test_search_filters(universe):
    frame, _ = universe
    only_etf = search(frame, "", types=[ETF])
    assert list(only_etf["symbol"]) == ["QQQ"]
    nyse = search(frame, "", exchanges=["NYSE"])
    assert set(nyse["exchange"]) == {"NYSE"}
    assert search(frame, "", only_with_filings=True)["cik"].notna().all()


def test_bad_sec_schema_rejected():
    with pytest.raises(ValueError):
        build_universe(NASDAQ, OTHER, {"fields": ["x"], "data": []})


REQUIRED = ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "JPM", "XOM", "WMT", "TSLA", "BRK.B"]


def test_bundled_snapshot_covers_required_tickers_with_ciks():
    loaded = read_universe(BUNDLED_DATA_DIR)
    assert loaded is not None, "data/universe.csv missing"
    frame, meta = loaded
    rows = frame.set_index("symbol")
    for symbol in REQUIRED:
        assert symbol in rows.index, symbol
        assert pd.notna(rows.loc[symbol, "cik"]), symbol
        assert rows.loc[symbol, "is_company"], symbol
    assert meta["total_securities"] > 10_000
    assert meta["companies"] > 5_000
    assert {"Nasdaq", "NYSE", "NYSE American"} <= set(frame["exchange"])
