"""CSV export (with explicit units and formula-injection protection) and CSV import validation."""
from __future__ import annotations

import io

import pandas as pd

from fip.formatting import SCALES
from fip.xbrl import METRICS, CompanyFinancials, filing_index_url

MAX_UPLOAD_BYTES = 1_000_000
MAX_UPLOAD_ROWS = 500
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value):
    """Neutralise spreadsheet formula injection in text cells (OWASP CSV injection)."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    safe = frame.copy()
    for col in safe.columns:
        if safe[col].dtype == object:
            safe[col] = safe[col].map(sanitize_cell)
    return safe.to_csv(index=False).encode("utf-8-sig")  # BOM so Excel detects UTF-8


def long_format(items: list[tuple[str, CompanyFinancials]]) -> pd.DataFrame:
    """Tidy export: one row per company × fiscal year × metric, with full provenance."""
    rows = []
    for symbol, fin in items:
        for p in fin.periods:
            for key, fact in p.values.items():
                spec = METRICS[key]
                rows.append({
                    "symbol": symbol, "company": fin.entity_name, "cik": fin.cik,
                    "fiscal_year": p.fiscal_year, "period_start": p.start, "period_end": p.end,
                    "metric": key, "metric_label": spec.label, "statement": spec.statement,
                    "value": fact.value,
                    "unit": f"{fin.currency}/share" if spec.kind == "per_share" else fin.currency,
                    "scale": "per share" if spec.kind == "per_share" else "units (not thousands or millions)",
                    "derived": fact.derived, "formula_or_concept": fact.formula or f"{fin.taxonomy}:{fact.concept}",
                    "form": fact.form, "filed": fact.filed, "accession": fact.accession,
                    "filing_index": filing_index_url(fin.cik, fact.accession) if fact.accession else "",
                    "data_origin": fin.origin, "retrieved_at": fin.retrieved_at,
                })
    return pd.DataFrame(rows)


class CsvImportError(ValueError):
    pass


def read_user_csv(data: bytes, input_scale: str = "M") -> pd.DataFrame:
    """Validate an uploaded CSV with columns fiscal_year (or year), revenue, net_income.

    Optional columns: operating_income, gross_profit, operating_cash_flow, capex,
    total_assets, total_liabilities. ``input_scale`` is the scale the user states the
    file is in (K/M/B/units); values are converted to base units.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise CsvImportError("File is larger than 1 MB.")
    if input_scale not in SCALES:
        raise CsvImportError("Unknown unit scale.")
    try:
        frame = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False, nrows=MAX_UPLOAD_ROWS + 1)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        raise CsvImportError(f"Could not parse CSV ({type(exc).__name__}).") from None
    if len(frame) > MAX_UPLOAD_ROWS:
        raise CsvImportError(f"At most {MAX_UPLOAD_ROWS} rows are supported.")
    frame.columns = [str(c).strip().lower().replace(" ", "_") for c in frame.columns]
    if "fiscal_year" not in frame.columns and "year" in frame.columns:
        frame = frame.rename(columns={"year": "fiscal_year"})
    required = {"fiscal_year", "revenue", "net_income"}
    missing = required - set(frame.columns)
    if missing:
        raise CsvImportError("Missing required column(s): " + ", ".join(sorted(missing))
                             + ". Expected fiscal_year (or year), revenue, net_income.")

    optional = ["gross_profit", "operating_income", "operating_cash_flow", "capex", "total_assets",
                "total_liabilities", "total_equity"]
    keep = ["fiscal_year", "revenue", "net_income"] + [c for c in optional if c in frame.columns]
    out = frame[keep].copy()
    for col in keep:
        cleaned = out[col].astype(str).str.replace(r"[,\s$]", "", regex=True).str.replace(r"^\((.*)\)$", r"-\1", regex=True)
        out[col] = pd.to_numeric(cleaned.replace("", None), errors="coerce")
    bad = out[["fiscal_year", "revenue", "net_income"]].isna().any(axis=1)
    if bad.all():
        raise CsvImportError("No rows contain numeric fiscal_year, revenue and net_income values.")
    out = out[~bad].copy()
    out["fiscal_year"] = out["fiscal_year"].astype(int)
    if not out["fiscal_year"].between(1900, 2100).all():
        raise CsvImportError("fiscal_year values must be between 1900 and 2100.")
    if out["fiscal_year"].duplicated().any():
        raise CsvImportError("Duplicate fiscal years found; provide one row per fiscal year.")
    divisor = SCALES[input_scale][0]
    for col in keep[1:]:
        out[col] = out[col] * divisor
    return out.sort_values("fiscal_year").reset_index(drop=True)


def user_csv_to_financials(frame: pd.DataFrame, currency: str = "USD", name: str = "Uploaded company") -> CompanyFinancials:
    """Wrap validated upload rows in the same structure as SEC data so all analytics reuse one code path."""
    from fip.xbrl import AnnualPeriod, Fact
    periods = []
    for _, row in frame.iterrows():
        fy = int(row["fiscal_year"])
        values = {}
        for key in frame.columns:
            if key == "fiscal_year" or pd.isna(row[key]):
                continue
            values[key] = Fact(value=float(row[key]), concept="user upload", filed="", form="CSV", accession="")
        if "operating_cash_flow" in values and "capex" in values:
            values["free_cash_flow"] = Fact(value=values["operating_cash_flow"].value - abs(values["capex"].value),
                                            concept="Operating cash flow − capex", filed="", form="CSV",
                                            accession="", derived=True, formula="operating_cash_flow − capex")
        periods.append(AnnualPeriod(fiscal_year=fy, start=f"{fy}-01-01", end=f"{fy}-12-31", form="CSV",
                                    accession="", filed="", values=values))
    return CompanyFinancials(cik=0, entity_name=name, taxonomy="user upload", currency=currency, periods=periods,
                             origin="user upload", warnings=["User-supplied figures; not verified against SEC filings. "
                                                             "Period dates are approximated as calendar years."])
