"""Latest SEC filings for a company, explained in plain English.

Source: the SEC submissions JSON (``data.sec.gov/submissions/CIK##########.json``), which
EDGAR updates within minutes of each filing. Nothing here is news commentary or AI output:
every line is a filing that exists on EDGAR, labelled from SEC's own form type and 8-K item
numbers, with a link to the document.
"""
from __future__ import annotations

from dataclasses import dataclass

from fip.filings import document_url

# Forms an ordinary reader cares about. Everything else is grouped as "Other filing".
FORMS = {
    "10-K": ("Annual report", "annual", "Full-year audited financial statements and the business review."),
    "10-K/A": ("Annual report (amended)", "annual", "A correction or addition to an earlier annual report."),
    "20-F": ("Annual report", "annual", "Full-year audited financial statements (foreign company)."),
    "20-F/A": ("Annual report (amended)", "annual", "A correction to an earlier annual report."),
    "40-F": ("Annual report", "annual", "Full-year audited financial statements (Canadian company)."),
    "10-Q": ("Quarterly report", "quarterly", "Unaudited results for the latest quarter."),
    "10-Q/A": ("Quarterly report (amended)", "quarterly", "A correction to an earlier quarterly report."),
    "6-K": ("Current report (foreign company)", "event", "News a foreign company released at home, filed with the SEC."),
    "8-K": ("Current report", "event", "The company announced a material event."),
    "8-K/A": ("Current report (amended)", "event", "An update to an earlier event report."),
    "DEF 14A": ("Proxy statement", "governance", "Agenda for the shareholder meeting: board votes and executive pay."),
    "4": ("Insider trade", "insider", "A director, officer or 10% owner bought or sold shares."),
    "3": ("New insider", "insider", "Someone became an insider and disclosed their holdings."),
    "144": ("Planned insider sale", "insider", "Notice that an insider intends to sell restricted shares."),
    "SC 13G": ("Large shareholder (passive)", "ownership", "An investor now owns more than 5% and is passive."),
    "SC 13G/A": ("Large shareholder update", "ownership", "A 5%+ passive owner changed their position."),
    "SC 13D": ("Large shareholder (active)", "ownership", "An investor owns more than 5% and may seek influence."),
    "SC 13D/A": ("Large shareholder update (active)", "ownership", "A 5%+ active owner changed their position."),
    "S-1": ("Share offering registration", "capital", "The company registered new shares to sell."),
    "S-3": ("Shelf registration", "capital", "The company registered securities it may sell later."),
    "424B2": ("Securities offering", "capital", "Final terms of notes or shares being sold."),
    "424B5": ("Securities offering", "capital", "Final terms of shares or notes being sold."),
    "SD": ("Conflict-minerals report", "other", "Annual supply-chain disclosure."),
    "DEFA14A": ("Extra shareholder-meeting material", "governance", "Additional material for an upcoming shareholder vote."),
    "PX14A6G": ("Shareholder campaign letter", "governance", "An investor is urging other shareholders how to vote."),
    "DEF 14C": ("Shareholder information statement", "governance", "Notice of a corporate action approved without a vote."),
    "PRE 14C": ("Draft information statement", "governance", "Preliminary notice of a corporate action."),
    "S-4": ("Merger or acquisition registration", "deal", "Shares registered to pay for a merger or acquisition."),
    "S-4/A": ("Merger registration (amended)", "deal", "An update to a merger or acquisition registration."),
    "S-3ASR": ("Shelf registration", "capital", "The company registered securities it may sell later."),
    "11-K": ("Employee savings-plan report", "other", "Annual report of the employee stock or savings plan."),
    "ARS": ("Glossy annual report", "annual", "The annual report mailed to shareholders."),
    "13F-HR": ("Holdings report (as an investor)", "other", "Stocks the company itself holds as an institutional investor."),
}
# SEC renamed beneficial-ownership forms in 2024 ("SC 13G" -> "SCHEDULE 13G"); treat both the same.
for _old, _new in (("SC 13G", "SCHEDULE 13G"), ("SC 13G/A", "SCHEDULE 13G/A"), ("SC 13D", "SCHEDULE 13D"),
                   ("SC 13D/A", "SCHEDULE 13D/A")):
    FORMS[_new] = FORMS[_old]

# 8-K item numbers (SEC Form 8-K General Instructions) → plain English. Ordered by importance.
EIGHT_K_ITEMS = {
    "4.02": ("Earlier financial statements should no longer be relied on", "alert"),
    "1.05": ("Material cybersecurity incident", "alert"),
    "3.01": ("Exchange listing problem or delisting notice", "alert"),
    "2.06": ("Material impairment (write-down)", "alert"),
    "1.03": ("Bankruptcy or receivership", "alert"),
    "4.01": ("Change of auditor", "alert"),
    "2.02": ("Earnings results released", "results"),
    "2.01": ("Acquisition or sale of assets completed", "deal"),
    "1.01": ("Material agreement signed", "deal"),
    "1.02": ("Material agreement ended", "deal"),
    "2.03": ("New debt or financial obligation", "capital"),
    "2.05": ("Restructuring or exit costs", "deal"),
    "3.02": ("Unregistered sale of shares", "capital"),
    "3.03": ("Change to shareholder rights", "governance"),
    "5.01": ("Change in control", "governance"),
    "5.02": ("Director or executive change", "people"),
    "5.03": ("Bylaws or fiscal-year change", "governance"),
    "5.07": ("Shareholder vote results", "governance"),
    "7.01": ("Investor presentation / Reg FD disclosure", "info"),
    "8.01": ("Other company announcement", "info"),
    "9.01": ("Exhibits attached", "info"),
}
ITEM_EXPLAINED = {
    "2.02": "Usually the earnings press release for a quarter or full year.",
    "5.02": "A director or senior executive joined, left, or had a pay arrangement changed.",
    "8.01": "An announcement the company chose to file with the SEC.",
    "7.01": "Slides or other material the company shared with investors.",
    "1.01": "The company signed a significant contract.",
    "1.02": "A significant contract was ended.",
    "2.01": "The company finished buying or selling a business or major assets.",
    "2.03": "The company took on new debt or a similar obligation.",
    "2.05": "The company announced job cuts, closures or other restructuring costs.",
    "2.06": "The company wrote down the value of some assets.",
    "5.07": "Results of the votes at the shareholder meeting.",
    "5.03": "The company changed its bylaws or its fiscal year.",
    "4.02": "The company says previously reported numbers contain errors and should not be relied on.",
    "4.01": "The company changed its auditing firm.",
    "1.05": "The company disclosed a significant cybersecurity incident.",
    "3.01": "The stock exchange flagged a listing-rule problem, or the company is leaving the exchange.",
    "1.03": "The company entered bankruptcy or receivership.",
    "5.01": "Control of the company changed hands.",
}
NOISE_FORMS = {"4", "3", "144", "4/A", "3/A", "144/A", "5", "424B2", "424B3", "424B5", "SD", "FWP", "S-8", "S-8 POS",
               "CORRESP", "UPLOAD", "25-NSE", "CERT", "CERTNYS", "CERTNAS", "EFFECT", "8-A12B", "8-A12G", "N-PX",
               "11-K", "ARS", "13F-HR", "13F-HR/A", "DEFA14C", "IRANNOTICE", "DEFA14A"}


@dataclass
class Event:
    form: str
    filing_date: str
    report_date: str
    accession: str
    title: str          # plain-English headline
    detail: str         # one sentence on what it means
    kind: str           # annual | quarterly | event | insider | ownership | governance | capital | other
    importance: str     # alert | high | normal | low
    items: list
    url: str

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def describe(form: str, items: str) -> tuple[str, str, str, str, list]:
    """(title, detail, kind, importance, item labels) for one filing."""
    title, kind, detail = FORMS.get(form, (f"Form {form} filing", "other", "Another SEC filing; open it for details."))
    labels = []
    importance = "low" if form in NOISE_FORMS else "normal"
    if form in ("10-K", "20-F", "40-F", "10-Q", "S-4"):
        importance = "high"
    codes = [c.strip() for c in (items or "").split(",") if c.strip()]
    if form.startswith("8-K") and codes:
        known = [(c, EIGHT_K_ITEMS[c]) for c in codes if c in EIGHT_K_ITEMS and c != "9.01"]
        labels = [label for _, (label, _) in known]
        if known:
            title = known[0][1][0]
            detail = ITEM_EXPLAINED.get(known[0][0], "A current report the company filed with the SEC.")
            if len(labels) > 1:
                detail += " Also: " + "; ".join(labels[1:]) + "."
            tags = {tag for _, (_, tag) in known}
            importance = "alert" if "alert" in tags else "high" if tags & {"results", "deal", "people"} else "normal"
    return title, detail, kind, importance, labels


def recent_events(submissions: dict, *, limit: int = 40, include_noise: bool = False) -> list[Event]:
    cik = int(submissions.get("cik") or 0)
    recent = (submissions.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    n = len(forms)

    def col(name):
        values = recent.get(name) or []
        return values if len(values) == n else [""] * n

    dates, reports, accns, docs, items = (col("filingDate"), col("reportDate"), col("accessionNumber"),
                                          col("primaryDocument"), col("items"))
    out = []
    for i, form in enumerate(forms):
        if not accns[i] or not dates[i]:
            continue
        title, detail, kind, importance, labels = describe(form, items[i])
        if importance == "low" and not include_noise:
            continue
        out.append(Event(form=form, filing_date=dates[i], report_date=reports[i] or "", accession=accns[i],
                         title=title, detail=detail, kind=kind, importance=importance, items=labels,
                         url=document_url(cik, accns[i], docs[i])))
    out.sort(key=lambda e: (e.filing_date, e.accession), reverse=True)
    return out[:limit]


def latest_annual_filing_date(events: list[Event]) -> str:
    return max((e.filing_date for e in events if e.kind == "annual"), default="")
