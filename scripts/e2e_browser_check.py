"""End-to-end browser verification + real screenshots (Playwright, Microsoft Edge).

Usage:  python scripts/e2e_browser_check.py http://localhost:8517 docs/screenshots

Fails (exit 1) if any page shows a Streamlit exception, if expected content is
missing, or if a CSV download is invalid. Writes docs/screenshots/*.png and
docs/screenshots/e2e_report.json.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8517"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
ERROR_MARKERS = ["This app has encountered an error", "Traceback (most recent call last)", "StreamlitAPIException"]
results: list[dict] = []


def settle(page: Page, timeout: float = 90) -> None:
    """Wait until Streamlit finished running and skeleton loaders are gone."""
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=timeout * 1000)
    deadline = time.time() + timeout
    while time.time() < deadline:
        running = page.locator('[data-testid="stStatusWidget"]').count()
        skeletons = page.locator(".fi-skel").count()
        if not running and not skeletons:
            page.wait_for_timeout(1200)   # let Plotly finish drawing
            if not page.locator('[data-testid="stStatusWidget"]').count():
                return
        page.wait_for_timeout(400)
    raise TimeoutError("app did not settle")


def check(page: Page, name: str, expect: list[str], shot: str | None = None, forbid: list[str] | None = None):
    text = page.inner_text("body")
    lower = text.lower()      # CSS text-transform changes the case inner_text reports
    problems = [m for m in ERROR_MARKERS if m in text]
    problems += [f"missing: {e}" for e in expect if e.lower() not in lower]
    problems += [f"forbidden: {f}" for f in (forbid or []) if f.lower() in lower]
    if shot:
        page.screenshot(path=str(OUT / shot), full_page=True)
    results.append({"check": name, "ok": not problems, "problems": problems, "screenshot": shot})
    print(("PASS " if not problems else "FAIL ") + name + ("" if not problems else f"  {problems}"), flush=True)


def visit(page: Page, path: str):
    page.goto(BASE + path, wait_until="domcontentloaded")
    settle(page)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1, accept_downloads=True)
        page = ctx.new_page()

        visit(page, "/?t=AAPL")
        check(page, "Overview AAPL (desktop)", ["Apple Inc.", "REVENUE", "NET PROFIT MARGIN", "USD", "10-K"],
              "01_overview_aapl.png")

        visit(page, "/explorer")
        box = page.get_by_placeholder("Ticker or company name")
        box.fill("berkshire")
        box.press("Enter")
        settle(page)
        # Result rows are drawn on a canvas grid (not DOM text); verify via the match counter + grid a11y rows.
        check(page, "Explorer search 'berkshire'", ["2 matches", "query: berkshire"], "02_explorer_search.png")
        # results grid (others are stats); the canvas grid keeps a hidden accessibility table -> textContent
        grid_text = page.locator('[data-testid="stDataFrame"]').first.evaluate("el => el.textContent")
        ok = "BRK.B" in grid_text and "BRK.A" in grid_text
        results.append({"check": "Explorer grid contains BRK.A and BRK.B", "ok": ok, "problems": [] if ok else [grid_text[:200]]})
        print(("PASS" if ok else "FAIL") + " explorer grid rows BRK.A/BRK.B", flush=True)
        box.fill("")
        box.press("Enter")
        settle(page)
        check(page, "Explorer default universe", ["matches", "Nasdaq", "NYSE"], None)

        visit(page, "/compare?t=AAPL")
        check(page, "Compare AAPL/MSFT/GOOGL/NVDA", ["AAPL", "MSFT", "GOOGL", "NVDA", "Net profit margin", "Period end"],
              "03_compare.png")

        visit(page, "/statements?t=JPM")
        check(page, "Statements JPM (bank)", ["Morgan", "Revenue", "Net income", "USD"], "04_statements_jpm.png")
        with page.expect_download(timeout=30000) as dl:
            page.get_by_text("All statements, long format").click()
        content = Path(dl.value.path()).read_bytes().decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content)))
        ok = bool(rows) and {"metric", "value", "unit", "accession", "filing_index"} <= set(rows[0])
        results.append({"check": "CSV download is valid", "ok": ok, "problems": [] if ok else ["bad csv"],
                        "rows": len(rows)})
        print(("PASS" if ok else "FAIL") + f" CSV download ({len(rows)} rows)", flush=True)

        visit(page, "/insights?t=NVDA")
        check(page, "Insights NVDA", ["NVIDIA", "Calculation", "Rule:"], "05_insights_nvda.png")

        visit(page, "/assistant?t=AAPL")
        check(page, "AI assistant page (no key exposure)", ["AI research assistant", "Free-tier models only"],
              "06_assistant.png", forbid=["AIza"])

        visit(page, "/sources?t=AAPL")
        check(page, "Sources & methodology", ["Primary data for this company", "Fiscal periods used"],
              "07_sources.png")

        visit(page, "/?t=TM")
        check(page, "Overview Toyota (20-F, JPY, IFRS)", ["Toyota", "JPY", "20-F"], "08_overview_toyota_ifrs.png")

        visit(page, "/?t=XOM")
        check(page, "XOM holding company: explained, not substituted", ["unavailable"], "09_xom_unavailable.png",
              forbid=["NET PROFIT MARGIN"])

        visit(page, "/?t=SPY")
        check(page, "ETF explained", ["not operating companies"], None)

        for symbol in ["GOOG", "AMZN", "META", "WMT", "TSLA", "BRK.B", "MSFT", "GOOGL", "NVDA", "JPM"]:
            visit(page, f"/?t={symbol}")
            check(page, f"Overview {symbol}", ["REVENUE", "SEC data"], None)   # live or cached (<12 h)

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                                     has_touch=True)
        m = mobile.new_page()
        visit(m, "/?t=MSFT")
        check(m, "Overview MSFT (mobile 390px)", ["Microsoft", "REVENUE"], "10_mobile_overview.png")
        overflow = m.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        results.append({"check": "No horizontal page overflow on mobile", "ok": not overflow, "problems": []})
        print(("FAIL" if overflow else "PASS") + " no horizontal overflow on mobile", flush=True)
        visit(m, "/compare")
        check(m, "Compare (mobile 390px)", ["AAPL", "MSFT"], "11_mobile_compare.png")

        tablet = browser.new_context(viewport={"width": 820, "height": 1180})
        t = tablet.new_page()
        visit(t, "/statements?t=AAPL")
        check(t, "Statements (tablet 820px)", ["Income statement", "Revenue"], "12_tablet_statements.png")
        browser.close()

    (OUT / "e2e_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
