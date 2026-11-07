"""Extract audited annual financial statements from SEC XBRL Company Facts.

Design rules (each one fixes a class of error seen in real filings):

1. **Annual only.** Facts must come from an annual report form (10-K, 20-F, 40-F
   and amendments) and, for flow metrics, cover 350–380 days. Quarterly and
   year-to-date values are never mixed in.
2. **Periods are the filer's own fiscal years.** A period is included only if it
   is the primary reporting period of some annual filing (its latest period end).
   The fiscal-year label comes from that filing's ``fy`` field, so Walmart's year
   ending 2026-01-31 is FY2026, as Walmart reports it.
3. **One taxonomy, one currency.** US-GAAP or IFRS is chosen by the most recent
   coverage; the reporting currency is the unit with the most annual periods
   (USD convenience translations of foreign filers are therefore not used).
4. **Latest filed value wins** for a given period (captures restatements and
   recasts). The originally reported value is kept so restatements are visible.
5. **Revenue = the largest total-revenue concept** reported for that period.
   Filers switch concepts over time and some report a narrower
   ``RevenueFromContractWithCustomer…`` next to total ``Revenues`` (insurers,
   banks, energy). The concept used is recorded for every value.
6. **Derived values are labelled** (e.g. free cash flow, gross profit computed as
   revenue − cost of revenue). Nothing is filled with zero or estimated.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone

ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A"}
MIN_DAYS, MAX_DAYS = 350, 380
RESTATEMENT_THRESHOLD = 0.005  # 0.5 %


class NoAnnualDataError(ValueError):
    """The registrant has no usable annual financial facts. ``user_message`` explains why."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    statement: str            # income | balance | cashflow
    kind: str                 # duration | instant | per_share
    concepts: dict            # taxonomy -> tuple of concepts (priority order)
    strategy: str = "priority"  # priority | max
    description: str = ""


METRICS: dict[str, MetricSpec] = {m.key: m for m in [
    MetricSpec("revenue", "Revenue", "income", "duration", {
        "us-gaap": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense",
                    "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet",
                    "RevenuesNetOfInterestExpenseAfterProvisionForLosses"),
        "ifrs-full": ("Revenue", "RevenueFromContractsWithCustomers", "RevenueFromSaleOfGoods"),
    }, "max", "Largest total-revenue concept reported for the fiscal year."),
    MetricSpec("cost_of_revenue", "Cost of revenue", "income", "duration", {
        "us-gaap": ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices"),
        "ifrs-full": ("CostOfSales",),
    }),
    MetricSpec("gross_profit", "Gross profit", "income", "duration", {
        "us-gaap": ("GrossProfit",), "ifrs-full": ("GrossProfit",),
    }, description="Reported gross profit; if not reported, revenue − cost of revenue (labelled derived)."),
    MetricSpec("operating_income", "Operating income", "income", "duration", {
        "us-gaap": ("OperatingIncomeLoss",), "ifrs-full": ("ProfitLossFromOperatingActivities",),
    }, description="Operating income (loss) as reported. Many banks and insurers do not report this subtotal."),
    MetricSpec("net_income", "Net income", "income", "duration", {
        "us-gaap": ("NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"),
        "ifrs-full": ("ProfitLossAttributableToOwnersOfParent", "ProfitLoss"),
    }, description="Net income attributable to the parent company's shareholders where reported."),
    MetricSpec("eps_diluted", "Diluted EPS", "income", "per_share", {
        "us-gaap": ("EarningsPerShareDiluted",), "ifrs-full": ("DilutedEarningsLossPerShare",),
    }),
    MetricSpec("total_assets", "Total assets", "balance", "instant", {
        "us-gaap": ("Assets",), "ifrs-full": ("Assets",),
    }),
    MetricSpec("total_liabilities", "Total liabilities", "balance", "instant", {
        "us-gaap": ("Liabilities",), "ifrs-full": ("Liabilities",),
    }, description="Reported total liabilities; otherwise total liabilities & equity − total equity (derived)."),
    MetricSpec("total_equity", "Shareholders' equity", "balance", "instant", {
        "us-gaap": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        "ifrs-full": ("EquityAttributableToOwnersOfParent", "Equity"),
    }, description="Equity attributable to the parent where reported."),
    MetricSpec("cash", "Cash & equivalents", "balance", "instant", {
        "us-gaap": ("CashAndCashEquivalentsAtCarryingValue",
                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "CashAndDueFromBanks"),
        "ifrs-full": ("CashAndCashEquivalents",),
    }),
    MetricSpec("operating_cash_flow", "Operating cash flow", "cashflow", "duration", {
        "us-gaap": ("NetCashProvidedByUsedInOperatingActivities",
                    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
        "ifrs-full": ("CashFlowsFromUsedInOperatingActivities",),
    }),
    MetricSpec("capex", "Capital expenditure", "cashflow", "duration", {
        "us-gaap": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
                    "PaymentsToAcquireOtherPropertyPlantAndEquipment"),
        "ifrs-full": ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                      "PurchaseOfPropertyPlantAndEquipment"),
    }, description="Cash paid for property, plant & equipment (shown as a positive outflow)."),
    MetricSpec("free_cash_flow", "Free cash flow", "cashflow", "duration", {},
               description="Derived: operating cash flow − capital expenditure."),
]}

_TOTAL_LIAB_AND_EQUITY = {"us-gaap": ("LiabilitiesAndStockholdersEquity",), "ifrs-full": ("EquityAndLiabilities",)}
_TOTAL_EQUITY_INCL_NCI = {"us-gaap": ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",),
                          "ifrs-full": ("Equity",)}
_NCI_PRESENT = {"us-gaap": ("MinorityInterest",), "ifrs-full": ("NoncontrollingInterests",)}


@dataclass
class Fact:
    value: float
    concept: str
    filed: str
    form: str
    accession: str
    derived: bool = False
    formula: str = ""
    original_value: float | None = None
    original_accession: str = ""

    @property
    def restated(self) -> bool:
        if self.original_value is None or self.derived:
            return False
        base = abs(self.original_value) or 1.0
        return abs(self.value - self.original_value) / base > RESTATEMENT_THRESHOLD


@dataclass
class AnnualPeriod:
    fiscal_year: int
    start: str
    end: str
    form: str            # form of the filing whose primary period this is
    accession: str
    filed: str
    values: dict = field(default_factory=dict)   # metric key -> Fact

    def value(self, key: str):
        fact = self.values.get(key)
        return None if fact is None else fact.value


@dataclass
class CompanyFinancials:
    cik: int
    entity_name: str
    taxonomy: str
    currency: str
    periods: list               # AnnualPeriod, ascending by end date
    warnings: list = field(default_factory=list)
    retrieved_at: str = ""
    origin: str = "live"        # live | disk cache | bundled snapshot
    excluded_note: str = ""

    @property
    def source_url(self) -> str:
        return companyfacts_url(self.cik)

    @property
    def latest(self) -> AnnualPeriod:
        return self.periods[-1]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CompanyFinancials":
        periods = []
        for p in data["periods"]:
            values = {k: Fact(**v) for k, v in p["values"].items()}
            periods.append(AnnualPeriod(**{**p, "values": values}))
        return cls(**{**data, "periods": periods})


def companyfacts_url(cik: int) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"


def filing_index_url(cik: int, accession: str) -> str:
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{accession}-index.htm")


# ---------------------------------------------------------------- helpers
def _days(start: str, end: str) -> int | None:
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except (TypeError, ValueError):
        return None


def _is_annual_duration(item: dict) -> bool:
    if item.get("form") not in ANNUAL_FORMS or "start" not in item:
        return False
    days = _days(item["start"], item.get("end", ""))
    return days is not None and MIN_DAYS <= days <= MAX_DAYS


def _numeric(item: dict) -> float | None:
    try:
        value = float(item["val"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if value == value else None  # drop NaN


def _currency_units(units: dict) -> dict:
    return {u: items for u, items in units.items() if len(u) == 3 and u.isalpha() and u.isupper()}


def _choose_taxonomy(facts: dict) -> str | None:
    best = None
    for taxonomy in ("us-gaap", "ifrs-full"):
        concepts = facts.get(taxonomy, {})
        ends = set()
        for key in ("revenue", "net_income"):
            for concept in METRICS[key].concepts.get(taxonomy, ()):
                for items in _currency_units(concepts.get(concept, {}).get("units", {})).values():
                    ends.update(i["end"] for i in items if _is_annual_duration(i))
        if ends:
            rank = (max(ends), len(ends))
            if best is None or rank > best[0]:
                best = (rank, taxonomy)
    return best[1] if best else None


def _choose_currency(concepts: dict, taxonomy: str) -> str:
    counts: Counter = Counter()
    for key in ("revenue", "net_income"):
        for concept in METRICS[key].concepts.get(taxonomy, ()):
            for unit, items in _currency_units(concepts.get(concept, {}).get("units", {})).items():
                counts[unit] += len({i["end"] for i in items if _is_annual_duration(i)})
    if not counts:
        return "USD"
    top = counts.most_common()
    best_unit, best_count = top[0]
    # On a tie prefer the non-USD unit: USD next to a local currency is a convenience translation.
    for unit, count in top[1:]:
        if count == best_count and best_unit == "USD" and unit != "USD":
            return unit
    return best_unit


def _primary_periods(concepts: dict, currency: str) -> dict:
    """Map period end -> metadata of the annual filing whose primary period it is."""
    ends_by_accn: dict[str, dict] = {}
    for concept in concepts.values():
        for unit, items in concept.get("units", {}).items():
            if unit != currency:
                continue
            for item in items:
                if not _is_annual_duration(item) or not item.get("accn"):
                    continue
                current = ends_by_accn.get(item["accn"])
                if current is None or item["end"] > current["end"]:
                    ends_by_accn[item["accn"]] = {
                        "end": item["end"], "start": item["start"], "fy": item.get("fy"),
                        "form": item["form"], "filed": item.get("filed", ""), "accession": item["accn"],
                    }
    periods: dict[str, dict] = {}
    for meta in ends_by_accn.values():
        existing = periods.get(meta["end"])
        # Keep the ORIGINAL filing (earliest filed) as the period's home filing.
        if existing is None or meta["filed"] < existing["filed"]:
            periods[meta["end"]] = meta
    return periods


def _select_fact(concepts: dict, names, currency: str, end: str, kind: str, strategy: str) -> Fact | None:
    unit = currency if kind != "per_share" else f"{currency}/shares"
    candidates = []
    for priority, concept_name in enumerate(names):
        items = concepts.get(concept_name, {}).get("units", {}).get(unit, [])
        matches = []
        for item in items:
            if item.get("end") != end or item.get("form") not in ANNUAL_FORMS:
                continue
            if kind == "instant":
                if "start" in item:
                    continue
            elif not _is_annual_duration(item):
                continue
            value = _numeric(item)
            if value is not None:
                matches.append((item.get("filed", ""), value, item))
        if not matches:
            continue
        matches.sort(key=lambda m: m[0])
        original, latest = matches[0], matches[-1]
        fact = Fact(
            value=latest[1], concept=concept_name, filed=latest[0], form=latest[2].get("form", ""),
            accession=latest[2].get("accn", ""), original_value=original[1],
            original_accession=original[2].get("accn", ""),
        )
        candidates.append((priority, fact))
        if strategy == "priority":
            break
    if not candidates:
        return None
    if strategy == "max":
        return max(candidates, key=lambda c: (c[1].value, -c[0]))[1]
    return candidates[0][1]


def _derive(label: str, value: float, formula: str, inputs: list[Fact]) -> Fact:
    latest = max(inputs, key=lambda f: f.filed)
    return Fact(value=value, concept=label, filed=latest.filed, form=latest.form, accession=latest.accession,
                derived=True, formula=formula)


def _fiscal_year_label(meta: dict) -> int:
    end_year = int(meta["end"][:4])
    fy = meta.get("fy")
    if isinstance(fy, int) and end_year - 1 <= fy <= end_year + 1:
        return fy
    return end_year


# ---------------------------------------------------------------- public API
def extract_financials(companyfacts: dict, *, max_periods: int = 10, today: date | None = None) -> CompanyFinancials:
    cik = int(companyfacts.get("cik") or 0)
    name = companyfacts.get("entityName") or ""
    facts = companyfacts.get("facts") or {}

    taxonomy = _choose_taxonomy(facts)
    if taxonomy is None:
        forms = Counter()
        for tax in facts.values():
            for concept in tax.values():
                for items in concept.get("units", {}).values():
                    forms.update(i.get("form") for i in items)
        if not facts:
            detail = "SEC holds no XBRL financial facts for this registrant."
        else:
            top = ", ".join(f"{f} ({n})" for f, n in forms.most_common(3) if f)
            detail = f"Facts exist only from other forms: {top}." if top else "No annual facts were found."
        raise NoAnnualDataError(
            "No audited annual revenue or net income (10-K / 20-F / 40-F XBRL) is available for this registrant. "
            + detail + " New registrants, holding-company reorganisations, funds and some foreign filers "
            "commonly fall in this category."
        )

    concepts = facts[taxonomy]
    currency = _choose_currency(concepts, taxonomy)
    primary = _primary_periods(concepts, currency)

    periods: list[AnnualPeriod] = []
    for end in sorted(primary):
        meta = primary[end]
        period = AnnualPeriod(fiscal_year=_fiscal_year_label(meta), start=meta["start"], end=end,
                              form=meta["form"], accession=meta["accession"], filed=meta["filed"])
        for key, spec in METRICS.items():
            names = spec.concepts.get(taxonomy, ())
            if names:
                fact = _select_fact(concepts, names, currency, end, spec.kind, spec.strategy)
                if fact is not None:
                    period.values[key] = fact
        if "revenue" not in period.values and "net_income" not in period.values:
            continue
        _add_derived(period, concepts, taxonomy, currency)
        periods.append(period)

    if not periods:
        raise NoAnnualDataError("Annual filings exist, but none contain revenue or net income in the reporting currency.")

    periods = periods[-max_periods:]
    warnings = _consistency_warnings(periods, today or date.today())
    other = "ifrs-full" if taxonomy == "us-gaap" else "us-gaap"
    excluded = ""
    if other in facts and _choose_taxonomy({other: facts[other]}):
        excluded = (f"Older annual data reported under {'IFRS' if other == 'ifrs-full' else 'US GAAP'} is not "
                    "combined with the current accounting basis.")
    return CompanyFinancials(
        cik=cik, entity_name=name, taxonomy=taxonomy, currency=currency, periods=periods, warnings=warnings,
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), excluded_note=excluded,
    )


def _add_derived(period: AnnualPeriod, concepts: dict, taxonomy: str, currency: str) -> None:
    v = period.values
    if "gross_profit" not in v and "revenue" in v and "cost_of_revenue" in v:
        v["gross_profit"] = _derive("Revenue − cost of revenue", v["revenue"].value - v["cost_of_revenue"].value,
                                    "revenue − cost_of_revenue", [v["revenue"], v["cost_of_revenue"]])
    if "total_liabilities" not in v:
        total = _select_fact(concepts, _TOTAL_LIAB_AND_EQUITY.get(taxonomy, ()), currency, period.end,
                             "instant", "priority")
        equity_all = _select_fact(concepts, _TOTAL_EQUITY_INCL_NCI.get(taxonomy, ()), currency, period.end,
                                  "instant", "priority")
        if equity_all is None:
            nci = _select_fact(concepts, _NCI_PRESENT.get(taxonomy, ()), currency, period.end, "instant", "priority")
            parent = v.get("total_equity")
            if nci is None and parent is not None and parent.concept in ("StockholdersEquity",
                                                                          "EquityAttributableToOwnersOfParent"):
                equity_all = parent  # no non-controlling interest reported -> parent equity is total equity
        if total is not None and equity_all is not None:
            v["total_liabilities"] = _derive("Liabilities & equity − total equity", total.value - equity_all.value,
                                             "total_liabilities_and_equity − total_equity", [total, equity_all])
    if "operating_cash_flow" in v and "capex" in v:
        v["free_cash_flow"] = _derive("Operating cash flow − capex",
                                      v["operating_cash_flow"].value - abs(v["capex"].value),
                                      "operating_cash_flow − capital_expenditure",
                                      [v["operating_cash_flow"], v["capex"]])


def _consistency_warnings(periods: list[AnnualPeriod], today: date) -> list[str]:
    warnings = []
    labels = [p.fiscal_year for p in periods]
    if len(set(labels)) != len(labels) or labels != sorted(labels):
        for p in periods:
            p.fiscal_year = int(p.end[:4])
        warnings.append("Fiscal-year labels in the filings were inconsistent; years are labelled by period-end year.")
    if len(periods) > 1:
        ends = [date.fromisoformat(p.end) for p in periods]
        # 52/53-week fiscal years drift by a few days; flag only genuine year-end changes.
        ref = ends[-1].timetuple().tm_yday
        drift = max(min(abs(e.timetuple().tm_yday - ref), 366 - abs(e.timetuple().tm_yday - ref)) for e in ends)
        if drift > 14:
            warnings.append("The fiscal year-end changed during this history; adjacent years may not be comparable.")
        gaps = [(b - a).days for a, b in zip(ends, ends[1:])]
        if any(g > 390 for g in gaps):
            warnings.append("Some fiscal years are missing from the XBRL record; growth is not computed across gaps.")
    latest_end = date.fromisoformat(periods[-1].end)
    if (today - latest_end).days > 550:
        warnings.append(f"The most recent annual report in SEC XBRL data covers the period ending {periods[-1].end}; "
                        "a newer annual report may not be available in structured form.")
    restated = sorted({p.fiscal_year for p in periods for f in p.values.values() if f.restated})
    if restated:
        warnings.append("Values for FY " + ", ".join(map(str, restated)) + " were revised in later filings; "
                        "the latest filed figures are shown.")
    return warnings
