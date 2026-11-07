"""Registrant profile and annual-report filing links from SEC submissions metadata."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from fip.sectors import sector_for_sic

ANNUAL_REPORT_FORMS = {"10-K", "10-K/A", "10-KT", "20-F", "20-F/A", "40-F", "40-F/A"}
FORM_DESCRIPTIONS = {
    "10-K": "Annual report (US domestic issuer)",
    "10-K/A": "Amended annual report",
    "10-KT": "Transition-period annual report",
    "20-F": "Annual report (foreign private issuer)",
    "20-F/A": "Amended annual report (foreign private issuer)",
    "40-F": "Annual report (Canadian issuer, MJDS)",
    "40-F/A": "Amended annual report (Canadian issuer)",
}


@dataclass
class Filing:
    form: str
    filing_date: str
    report_date: str
    accession: str
    primary_document: str
    url: str
    index_url: str


@dataclass
class CompanyProfile:
    cik: int
    name: str
    tickers: list = field(default_factory=list)
    exchanges: list = field(default_factory=list)
    sic: str = ""
    sic_description: str = ""
    sector: str = "Unclassified"
    owner_org: str = ""
    fiscal_year_end: str = ""        # MMDD
    state_of_incorporation: str = ""
    location: str = ""
    entity_type: str = ""
    filer_category: str = ""
    former_names: list = field(default_factory=list)
    annual_filings: list = field(default_factory=list)  # Filing dicts, newest first

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def fiscal_year_end_label(self) -> str:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        fye = self.fiscal_year_end
        if len(fye) == 4 and fye.isdigit() and 1 <= int(fye[:2]) <= 12:
            return f"{months[int(fye[:2]) - 1]} {int(fye[2:])}"
        return "—"

    @property
    def edgar_url(self) -> str:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={self.cik:010d}&type=10-K&dateb=&owner=include&count=40"


def submissions_url(cik: int) -> str:
    return f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"


def document_url(cik: int, accession: str, primary_document: str) -> str:
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    return base + primary_document if primary_document else base


def parse_submissions(data: dict) -> CompanyProfile:
    cik = int(data.get("cik") or 0)
    business = (data.get("addresses") or {}).get("business") or {}
    city = (business.get("city") or "").title()
    region = (business.get("country") or business.get("stateOrCountryDescription")
              or business.get("stateOrCountry") or "")
    if isinstance(region, str) and region.isupper() and len(region) > 3:
        region = region.title()
    location = ", ".join(x for x in (city, region) if x)

    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    annual = []
    for i, form in enumerate(forms):
        if form not in ANNUAL_REPORT_FORMS:
            continue
        try:
            accession = recent["accessionNumber"][i]
            primary = (recent.get("primaryDocument") or [""] * len(forms))[i] or ""
            annual.append(Filing(
                form=form,
                filing_date=recent["filingDate"][i],
                report_date=(recent.get("reportDate") or [""] * len(forms))[i] or "",
                accession=accession,
                primary_document=primary,
                url=document_url(cik, accession, primary),
                index_url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{accession}-index.htm",
            ).__dict__)
        except (KeyError, IndexError):
            continue
    annual.sort(key=lambda f: f["filing_date"], reverse=True)

    sic = str(data.get("sic") or "")
    return CompanyProfile(
        cik=cik,
        name=data.get("name") or "",
        tickers=list(data.get("tickers") or []),
        exchanges=[e for e in (data.get("exchanges") or []) if e],
        sic=sic,
        sic_description=data.get("sicDescription") or "",
        sector=sector_for_sic(sic) if sic else "Unclassified",
        owner_org=data.get("ownerOrg") or "",
        fiscal_year_end=data.get("fiscalYearEnd") or "",
        state_of_incorporation=data.get("stateOfIncorporationDescription") or data.get("stateOfIncorporation") or "",
        location=location,
        entity_type=data.get("entityType") or "",
        filer_category=data.get("category") or "",
        former_names=[n.get("name", "") for n in (data.get("formerNames") or []) if n.get("name")][:5],
        annual_filings=annual[:20],
    )


def filing_for_accession(profile: CompanyProfile | None, accession: str) -> dict | None:
    if profile is None:
        return None
    for filing in profile.annual_filings:
        if filing["accession"] == accession:
            return filing
    return None
