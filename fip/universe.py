"""The searchable universe of US exchange-listed securities.

Sources (all official, free, refreshed daily by their publishers):

* Nasdaq Trader ``nasdaqlisted.txt`` — every Nasdaq-listed security.
* Nasdaq Trader ``otherlisted.txt`` — NYSE, NYSE American, NYSE Arca, Cboe BZX
  and IEX listings.
* SEC ``company_tickers_exchange.json`` — ticker → CIK (SEC registrant id).
* Optional ``data/sec_profiles.csv`` — SIC industry codes etc. pulled from SEC
  submissions metadata by ``scripts/build_sec_profiles.py``.

Listings are the source of truth for *what trades*; the SEC file is used only to
attach the registrant (CIK) whose filings hold the financial statements. A
security without a CIK match stays discoverable but is clearly labelled as having
no SEC financial record — the app never borrows another registrant's data.
"""
from __future__ import annotations

import io
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from fip.config import BUNDLED_DATA_DIR, cache_dir, sec_contact_email
from fip.http_client import DataSourceError, fetch
from fip.sectors import sector_for_sic

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

UNIVERSE_FILE = "universe.csv"
UNIVERSE_META_FILE = "universe_meta.json"
PROFILES_FILE = "sec_profiles.csv"
REFRESH_AFTER_SECONDS = 24 * 3600

OTHER_EXCHANGES = {
    "N": "NYSE",
    "A": "NYSE American",
    "P": "NYSE Arca",
    "Z": "Cboe BZX",
    "V": "IEX",
}
NASDAQ_TIERS = {"Q": "Nasdaq Global Select", "G": "Nasdaq Global Market", "S": "Nasdaq Capital Market"}
FINANCIAL_STATUS = {
    "D": "Deficient", "E": "Delinquent", "Q": "Bankrupt", "N": "Normal",
    "G": "Deficient and bankrupt", "H": "Deficient and delinquent",
    "J": "Delinquent and bankrupt", "K": "Deficient, delinquent and bankrupt",
}
SEC_ONLY_EXCHANGES = {"TXSE"}
SEC_EXCHANGE_LABELS = {"TXSE": "Texas Stock Exchange", "CBOE": "Cboe BZX"}

COMMON = "Common stock"
ADR = "ADR / foreign issuer"
ETF = "ETF"
ETN = "ETN"
FUND = "Closed-end fund / trust"
PREFERRED = "Preferred / depositary"
WARRANT = "Warrant"
RIGHT = "Right"
UNIT = "Unit"
NOTE = "Notes / debt"
OTHER = "Other"
COMPANY_TYPES = (COMMON, ADR)
INSTRUMENT_TYPES = [COMMON, ADR, ETF, ETN, FUND, PREFERRED, WARRANT, RIGHT, UNIT, NOTE, OTHER]

COLUMNS = [
    "symbol", "sec_ticker", "name", "security_name", "exchange", "market_tier", "instrument_type",
    "is_company", "cik", "sec_name", "sic", "sic_description", "sector", "country", "fiscal_year_end",
    "financial_status", "listing_source",
]


# ---------------------------------------------------------------- symbols
def to_sec_ticker(symbol: str) -> str:
    """Convert a Nasdaq Trader/CQS-style symbol to SEC's ticker convention.

    ``BRK.B`` → ``BRK-B``, ``BAC$K`` → ``BAC-PK``, ``AAC.U`` → ``AAC-UN``,
    ``AAC.W`` → ``AAC-WT``, ``AIIA.R`` → ``AIIA-RT``.
    """
    s = symbol.strip().upper()
    if "$" in s:
        root, _, series = s.partition("$")
        return f"{root}-P{series}"
    if "." in s:
        root, _, suffix = s.partition(".")
        suffix = {"U": "UN", "W": "WT", "WS": "WT", "R": "RT"}.get(suffix, suffix)
        return f"{root}-{suffix}"
    return s


def to_display_symbol(sec_ticker: str) -> str:
    """SEC ``BRK-B`` → widely used ``BRK.B``; preferred ``BAC-PK`` stays as-is."""
    if re.fullmatch(r"[A-Z]+-[A-Z]", sec_ticker):
        return sec_ticker.replace("-", ".")
    return sec_ticker


def symbol_key(text: str) -> str:
    """Separator-insensitive key: BRK.B / BRK-B / BRK/B / 'brk b' → BRKB."""
    return re.sub(r"[^A-Z0-9]", "", str(text).upper())


# ---------------------------------------------------------------- classification
_NAME_SUFFIX = re.compile(
    r"\s*(-\s*)?(Class [A-Z]\b.*|Common Stock.*|Common Shares.*|Ordinary Shares?.*|Capital Stock.*|"
    r"American Depositary.*|New Common Stock.*|Common Units.*|Shares of Beneficial Interest.*|"
    r"Subordinate Voting Shares.*|Registered Shares.*)$",
    re.IGNORECASE,
)


def issuer_name(security_name: str) -> str:
    text = re.sub(r"\s+", " ", security_name).strip()
    if " - " in text:
        text = text.split(" - ")[0]
    cleaned = _NAME_SUFFIX.sub("", text).strip(" ,-")
    return cleaned or text


def classify(security_name: str, etf_flag: str = "N", symbol: str = "") -> str:
    name = f" {security_name.lower()} "
    if etf_flag.strip().upper() == "Y":
        return ETF
    # CQS-style suffixes in otherlisted.txt are unambiguous.
    if "$" in symbol:
        return PREFERRED
    suffix = symbol.partition(".")[2]
    if suffix in {"W", "WS"} or suffix.startswith("WS"):
        return WARRANT
    if suffix == "U":
        return UNIT
    if suffix == "R":
        return RIGHT
    if "exchange traded note" in name or " etn" in name:
        return ETN
    if re.search(r"\bwarrants?\b", name):
        return WARRANT
    if re.search(r"\brights?\b", name) and "rights agreement" not in name:
        return RIGHT
    if re.search(r"\bunits?\b", name) and "common units" not in name:
        return UNIT
    if "preferred" in name or "preference" in name or (
            re.search(r"depositary shares?,? each representing", name) and "%" in name):
        return PREFERRED
    if re.search(r"\bnotes?\b|debentures|\bbonds?\b due|% senior|subordinated", name):
        return NOTE
    if "american depositary" in name or re.search(r"\bads\b|\badr\b", name):
        return ADR
    if re.search(r"\bfund\b|\bmunicipal\b|\bincome trust\b|\bclosed[- ]end\b|\bportfolio\b", name):
        return FUND
    if re.search(r"common stock|common shares|ordinary shares?|capital stock|class [a-z] (common|ordinary|shares|stock)"
                 r"|common units|shares of beneficial interest|subordinate voting|registered shares|\bshares\b", name):
        return COMMON
    return OTHER


# ---------------------------------------------------------------- parsing
def _read_pipe_file(text: str) -> tuple[pd.DataFrame, str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    created = ""
    if lines and lines[-1].startswith("File Creation Time"):
        created = lines[-1].split(":", 1)[1].strip(" |")
        lines = lines[:-1]
    frame = pd.read_csv(io.StringIO("\n".join(lines)), sep="|", dtype=str, keep_default_na=False)
    return frame, created


def parse_nasdaq_listed(text: str) -> tuple[pd.DataFrame, str]:
    raw, created = _read_pipe_file(text)
    raw = raw[raw["Test Issue"].str.upper() != "Y"]
    out = pd.DataFrame({
        "symbol": raw["Symbol"].str.strip(),
        "security_name": raw["Security Name"].str.strip(),
        "exchange": "Nasdaq",
        "market_tier": raw["Market Category"].map(NASDAQ_TIERS).fillna(""),
        "financial_status": raw["Financial Status"].map(FINANCIAL_STATUS).fillna(""),
        "etf": raw["ETF"].str.strip(),
    })
    return out, created


def parse_other_listed(text: str) -> tuple[pd.DataFrame, str]:
    raw, created = _read_pipe_file(text)
    raw = raw[raw["Test Issue"].str.upper() != "Y"]
    codes = raw["Exchange"].str.strip()
    out = pd.DataFrame({
        "symbol": raw["ACT Symbol"].str.strip(),
        "security_name": raw["Security Name"].str.strip(),
        # Codes outside the published legend (seen: F, M) are kept visible, not guessed.
        "exchange": [OTHER_EXCHANGES.get(c, f"Other US exchange ({c})") for c in codes],
        "market_tier": "",
        "financial_status": "",
        "etf": raw["ETF"].str.strip(),
    })
    return out, created


def parse_sec_tickers(payload: dict) -> pd.DataFrame:
    fields = payload.get("fields") or []
    data = payload.get("data") or []
    if fields != ["cik", "name", "ticker", "exchange"]:
        raise ValueError(f"Unexpected SEC ticker file schema: {fields}")
    frame = pd.DataFrame(data, columns=fields)
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["cik"] = pd.to_numeric(frame["cik"], errors="coerce").astype("Int64")
    return frame.dropna(subset=["cik"]).drop_duplicates("ticker")


# ---------------------------------------------------------------- build
def build_universe(nasdaq_text: str, other_text: str, sec_payload: dict,
                   profiles: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    nasdaq, nasdaq_created = parse_nasdaq_listed(nasdaq_text)
    other, other_created = parse_other_listed(other_text)
    listings = pd.concat([nasdaq, other], ignore_index=True)
    listings["sec_ticker"] = listings["symbol"].map(to_sec_ticker)
    listings["instrument_type"] = [classify(n, e, s) for n, e, s in
                                   zip(listings["security_name"], listings["etf"], listings["symbol"])]
    listings["name"] = listings["security_name"].map(issuer_name)
    listings["listing_source"] = "Nasdaq Trader"
    listings = listings.drop_duplicates("sec_ticker", keep="first")

    sec = parse_sec_tickers(sec_payload)
    merged = listings.merge(
        sec.rename(columns={"name": "sec_name", "exchange": "sec_exchange", "ticker": "sec_ticker"}),
        on="sec_ticker", how="left",
    )

    # A security whose name carries no instrument keyword (e.g. "AMETEK, Inc.") but
    # whose exact ticker SEC maps to an operating registrant is an equity share.
    plain_equity = merged["instrument_type"].eq(OTHER) & merged["cik"].notna() & merged["etf"].ne("Y")
    merged.loc[plain_equity, "instrument_type"] = COMMON
    undocumented = merged["exchange"].str.startswith("Other US exchange") & merged["sec_exchange"].notna()
    merged.loc[undocumented, "exchange"] = merged.loc[undocumented, "sec_exchange"].astype(str).map(
        lambda e: SEC_EXCHANGE_LABELS.get(e, e))

    # Registrants SEC lists on an exchange that Nasdaq Trader does not cover
    # (Texas Stock Exchange). SEC-only Nasdaq/NYSE/Cboe tickers are NOT added: their
    # absence from the daily exchange directories almost always means a delisting
    # that SEC's ticker file has not caught up with yet.
    listed_keys = set(merged["sec_ticker"])
    extra = sec[sec["exchange"].isin(SEC_ONLY_EXCHANGES) & ~sec["ticker"].isin(listed_keys)].copy()
    # SEC encodes preferreds/warrants/units with suffixes; only keep plain share classes.
    extra = extra[extra["ticker"].str.fullmatch(r"[A-Z]{1,5}(-[A-Z])?")]
    if not extra.empty:
        extra_frame = pd.DataFrame({
            "symbol": extra["ticker"].map(to_display_symbol),
            "sec_ticker": extra["ticker"],
            "security_name": extra["name"],
            "name": extra["name"],
            "exchange": extra["exchange"].map(lambda e: SEC_EXCHANGE_LABELS.get(e, e)),
            "market_tier": "",
            "financial_status": "",
            "etf": "N",
            "instrument_type": COMMON,
            "listing_source": "SEC ticker file",
            "cik": extra["cik"],
            "sec_name": extra["name"],
            "sec_exchange": extra["exchange"],
        })
        merged = pd.concat([merged, extra_frame], ignore_index=True)

    merged["is_company"] = merged["instrument_type"].isin(COMPANY_TYPES)

    if profiles is not None and not profiles.empty:
        prof = profiles.copy()
        prof["cik"] = pd.to_numeric(prof["cik"], errors="coerce").astype("Int64")
        keep = [c for c in ("cik", "sic", "sic_description", "country", "fiscal_year_end") if c in prof.columns]
        merged = merged.merge(prof[keep].drop_duplicates("cik"), on="cik", how="left")
    for col in ("sic", "sic_description", "country", "fiscal_year_end"):
        if col not in merged.columns:
            merged[col] = ""
    merged["sic"] = merged["sic"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    merged["country"] = merged["country"].fillna("").astype(str)
    foreign = merged["instrument_type"].eq(COMMON) & merged["country"].ne("") & merged["country"].ne("United States")
    merged.loc[foreign, "instrument_type"] = ADR
    merged["sector"] = [sector_for_sic(s) if s else "Unclassified" for s in merged["sic"]]
    merged["cik"] = merged["cik"].astype("Int64")
    for col in COLUMNS:
        if col not in merged.columns:
            merged[col] = ""
    universe = merged[COLUMNS].fillna({c: "" for c in COLUMNS if c != "cik"})
    universe = universe.sort_values(["is_company", "symbol"], ascending=[False, True]).reset_index(drop=True)

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nasdaq_file_created": nasdaq_created,
        "other_file_created": other_created,
        "total_securities": int(len(universe)),
        "companies": int(universe["is_company"].sum()),
        "with_cik": int(universe["cik"].notna().sum()),
        "by_exchange": universe["exchange"].value_counts().to_dict(),
        "by_type": universe["instrument_type"].value_counts().to_dict(),
        "sources": [NASDAQ_LISTED_URL, OTHER_LISTED_URL, SEC_TICKERS_URL],
    }
    return universe, meta


def download_and_build(contact_email: str | None = None, profiles: pd.DataFrame | None = None):
    nasdaq = fetch(NASDAQ_LISTED_URL, sec=False).content.decode("utf-8", errors="replace")
    other = fetch(OTHER_LISTED_URL, sec=False).content.decode("utf-8", errors="replace")
    sec_payload = json.loads(fetch(SEC_TICKERS_URL, sec=True, contact_email=contact_email).content)
    if profiles is None:
        profiles = load_profiles()
    return build_universe(nasdaq, other, sec_payload, profiles)


# ---------------------------------------------------------------- persistence
def load_profiles() -> pd.DataFrame | None:
    path = BUNDLED_DATA_DIR / PROFILES_FILE
    if not path.exists():
        return None
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def save_universe(universe: pd.DataFrame, meta: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / (UNIVERSE_FILE + ".tmp")
    universe.to_csv(tmp, index=False)
    tmp.replace(directory / UNIVERSE_FILE)
    (directory / UNIVERSE_META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def read_universe(directory: Path) -> tuple[pd.DataFrame, dict] | None:
    path = directory / UNIVERSE_FILE
    meta_path = directory / UNIVERSE_META_FILE
    if not path.exists():
        return None
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame["cik"] = pd.to_numeric(frame["cik"], errors="coerce").astype("Int64")
    frame["is_company"] = frame["is_company"].astype(str).str.lower().eq("true")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return frame, meta


@dataclass
class UniverseState:
    frame: pd.DataFrame
    meta: dict
    origin: str            # "live refresh" | "local cache" | "bundled snapshot"
    warning: str = ""


def load_universe(allow_refresh: bool = True, contact_email: str | None = None) -> UniverseState:
    """Freshest available universe: runtime cache → live refresh → bundled snapshot.

    A refresh is attempted only when the runtime cache is older than 24 h. Failure
    falls back to an older copy and records a visible warning (never silent).
    """
    runtime_dir = cache_dir()
    cached = read_universe(runtime_dir)
    cached_age = None
    if cached is not None:
        cached_age = time.time() - (runtime_dir / UNIVERSE_FILE).stat().st_mtime
        if cached_age < REFRESH_AFTER_SECONDS:
            return UniverseState(cached[0], cached[1], "local cache")

    warning = ""
    if allow_refresh and not (contact_email or sec_contact_email()):
        allow_refresh = False   # fail fast: the SEC ticker file needs a contact User-Agent
        warning = "Live listing refresh is off until SEC_CONTACT_EMAIL is configured."
    if allow_refresh:
        try:
            frame, meta = download_and_build(contact_email)
            save_universe(frame, meta, runtime_dir)
            return UniverseState(frame, meta, "live refresh")
        except (DataSourceError, ValueError, OSError) as exc:
            message = getattr(exc, "user_message", str(exc))
            warning = f"Live listing refresh failed: {message}"

    if cached is not None:
        return UniverseState(cached[0], cached[1], "local cache", warning or "Listing cache is older than 24 hours.")
    bundled = read_universe(BUNDLED_DATA_DIR)
    if bundled is None:
        raise DataSourceError("No company universe is available: live refresh failed and no bundled snapshot exists.")
    return UniverseState(bundled[0], bundled[1], "bundled snapshot", warning)


# ---------------------------------------------------------------- search
def add_search_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["_sym"] = out["symbol"].str.upper()
    out["_key"] = out["symbol"].map(symbol_key)
    out["_name"] = (out["name"] + " " + out["sec_name"]).str.lower()
    return out


_TIER_RANK = {"Nasdaq Global Select": 0, "Nasdaq Global Market": 1, "Nasdaq Capital Market": 2}


def search(indexed: pd.DataFrame, query: str = "", *, exchanges=None, types=None, sectors=None,
           only_with_filings: bool = False) -> pd.DataFrame:
    """Ranked search over symbol and name. ``indexed`` comes from ``add_search_columns``."""
    frame = indexed
    if exchanges:
        frame = frame[frame["exchange"].isin(exchanges)]
    if types:
        frame = frame[frame["instrument_type"].isin(types)]
    if sectors:
        frame = frame[frame["sector"].isin(sectors)]
    if only_with_filings:
        frame = frame[frame["cik"].notna()]

    q = (query or "").strip()[:80]
    if not q:
        ranked = frame.assign(_score=0)
    else:
        q_upper, q_lower, q_key = q.upper(), q.lower(), symbol_key(q)
        escaped = re.escape(q_lower)
        score = pd.Series(0, index=frame.index, dtype="int64")
        name = frame["_name"]
        score = score.mask(name.str.contains(escaped, regex=True), 30)
        score = score.mask(name.str.contains(r"\b" + escaped, regex=True), 50)
        score = score.mask(name.str.startswith(q_lower), 60)
        if q_key:
            score = score.mask(frame["_key"].str.startswith(q_key), 80)
            score = score.mask(frame["_key"].eq(q_key), 95)
        score = score.mask(frame["_sym"].eq(q_upper), 100)
        ranked = frame.assign(_score=score)
        ranked = ranked[ranked["_score"] > 0]

    ranked = ranked.assign(
        _company=(~ranked["is_company"]).astype(int),
        _tier=ranked["market_tier"].map(_TIER_RANK).fillna(1),
        _len=ranked["symbol"].str.len(),
    )
    ranked = ranked.sort_values(["_score", "_company", "_tier", "_len", "symbol"],
                                ascending=[False, True, True, True, True])
    return ranked.drop(columns=["_score", "_company", "_tier", "_len"])


def share_classes(frame: pd.DataFrame, cik) -> list[str]:
    if cik is None or pd.isna(cik):
        return []
    rows = frame[(frame["cik"] == cik) & frame["is_company"]]
    return rows["symbol"].tolist()
