"""Smoke-test a running desktop build: render key pages and save screenshots.

Usage:  python scripts/smoke_exe.py http://localhost:8501 out_dir
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
failures = 0
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    for path, expect, shot in [("/?t=AAPL", "Apple", "exe_overview.png"), ("/explorer", "matches", "exe_explorer.png"),
                               ("/statements?t=MSFT", "Income statement", "exe_statements.png")]:
        page.goto(BASE + path)
        # Wait for real page content: a cold first run (fresh venv / first exe unpack) can take a while.
        page.wait_for_selector(".fi-eyebrow", timeout=240000)
        deadline = time.time() + 120
        while time.time() < deadline and (page.locator('[data-testid="stStatusWidget"]').count()
                                          or page.locator(".fi-skel").count()):
            page.wait_for_timeout(400)
        page.wait_for_timeout(1500)
        text = page.inner_text("body")
        ok = expect.lower() in text.lower() and "encountered an error" not in text
        failures += not ok
        page.screenshot(path=str(OUT / shot), full_page=True)
        notice = [line for line in text.splitlines() if "snapshot" in line.lower() or "SEC" in line][:2]
        print(("PASS " if ok else "FAIL ") + path, "|", " / ".join(notice)[:220])
    browser.close()
sys.exit(1 if failures else 0)
