# Verification report — Financial Intelligence Platform V7

Date: 2026-11-03 · Machine: Windows 11 Pro 10.0.26200, Python 3.10.11, Streamlit 1.65.0, Microsoft Edge (headless, via Playwright 1.64)

Every result below was produced by running the software here. Nothing was assumed.

## 1. Automated tests — `pytest`
**144 passed, 1 skipped**: the skipped test checks git tracking, and this folder is not a git checkout yet. All tests run offline (`FIP_OFFLINE=1`, temporary cache, no secrets) in about 12 s, and run again automatically inside `desktop/build_windows.ps1`. `python -m compileall` over every module: OK.

| Area | File | What is proven |
|---|---|---|
| Unit formatting | `test_formatting.py` | 416,161 USD M → `$416.16B`; 1,250,000 USD M → `$1.25T`; 845 USD M → `$845M`; 0.4031 → `40.31%`; full-unit SEC values are never treated as millions; pp, negatives, JPY/TWD/DKK, shared chart scale |
| XBRL parsing | `test_xbrl.py` | Quarterly and YTD exclusion; filer fiscal-year labels (Jan year-ends); leap-day year-ends; year-end change warning; restatement detection; largest total-revenue concept; concept switches over time; derived metrics labelled; no liabilities derivation when NCI exists; no FCF without capex; IFRS + local currency over USD convenience translation; 10-Q-only registrants rejected with an explanation |
| **Real filings** | `test_xbrl.py` | AAPL FY2025 revenue **$416,161M**, net income **$112,010M**; MSFT FY2024 $245,122M / $88,136M; WMT FY2025 (ends 2025-01-31) $680,985M; BRK FY2024 $371,433M (total, not contract revenue); JPM FY2024 $177,556M / $58,471M; NVDA FY2025 $130,497M; TSMC 20-F in TWD (IFRS); Toyota IFRS not mixed with older US GAAP; **XOM holding company (CIK 2115436) → no annual data, no substitution** |
| Ticker mapping & search | `test_universe.py` | `BRK.B↔BRK-B↔brkb`, `BAC$K↔BAC-PK`, units/warrants/rights; GOOG/GOOGL and BRK.A/BRK.B share a CIK; test issues, OTC and SEC-only (delisted) tickers excluded; TXSE listings kept; undocumented exchange codes; ranking; regex-safe input; **bundled universe contains AAPL, MSFT, GOOGL, GOOG, AMZN, NVDA, META, JPM, XOM, WMT, TSLA, BRK.B with CIKs** |
| HTTP / API errors | `test_http_and_data_service.py` | UA contact required; 429 + Retry-After; 500/502/503 retried ×4; 403/404 not retried; connection errors; offline mode; live → disk cache; stale-cache and bundled-snapshot fallbacks with visible notices; 404 / no-annual-data / config errors explained |
| Gemini (mocked) | `test_gemini_and_guard.py` | Key in header only; 503 retry; fallback on 503/404/429 **only among free models**; quota exhausted → graceful error with no paid fallback; 401/403/`API_KEY_INVALID` stop immediately; network error text never contains the key; safety block; empty answer; paid models rejected from config; thought parts hidden |
| Server-side AI guard | `test_gemini_and_guard.py` | Per-visitor cooldown and daily cap; a new session from the same IP doesn't reset limits; global per-minute and daily caps; limits persist across restarts; kill switch; raw IPs not stored; answer cache TTL; access-code brute-force throttle |
| CSV import/export | `test_metrics_insights_exports.py` | V6 sample format accepted; thousands separators, parentheses negatives, declared scale; size, row, duplicate and year validation; export is valid CSV with BOM, units, provenance and SEC links; formula-injection neutralised |
| Metrics & insights | `test_metrics_insights_exports.py` | Growth only on consecutive years and positive bases; margins undefined on non-positive revenue; CAGR; currency, date and GAAP/IFRS comparison warnings; insight categories and rules |
| Secret leakage | `test_security.py` | No key-like strings in the repo; secrets file gitignored; no API-key input in any page; key used in exactly one place (`generate(...)`); error details hidden; key not in URLs; release script excludes `secrets.toml` |
| All pages (headless) | `test_app_pages.py` | All 7 pages render without exceptions offline; snapshot labelled; XOM and SPY show explanations; Compare with 4 companies; Explorer search; **the configured key never appears in the rendered page**; **full AI flow with mocked Gemini (answer shown, cache hit, quota error)** |

## 2. Browser end-to-end — `scripts/e2e_browser_check.py` (real server, live SEC, Microsoft Edge)
**27 / 27 checks passed** (live SEC data). See `docs/screenshots/e2e_report.json` and the 12 screenshots in `docs/screenshots/`.

Bugs this pass found and fixed before the final run:
- Explorer → Overview crashed: the session key was modified after its widget had rendered. Fixed with an `on_click` callback.
- Mobile opened with the sidebar covering the content. Fixed with `initial_sidebar_state="auto"`.
- The Streamlit `h1` style overrode the title size on phones, and long SIC names were clipped.
- Toyota was labelled "United States" because of an EDGAR address-code edge case. Fixed in the profile builder, then all 5,551 profiles were rebuilt.
- ETFs with an SEC CIK (e.g. SPY) were routed to company financials. Now blocked.

Covered: Overview for AAPL and the 10 other required tickers (GOOG, AMZN, META, WMT, TSLA, BRK.B, MSFT, GOOGL, NVDA, JPM); Explorer search ("berkshire" → BRK.A + BRK.B in the grid); Compare with 4 companies; Statements for a bank (JPM); **CSV download parsed and validated**; Insights; AI page (no key exposure); Sources; Toyota (20-F, JPY, IFRS); XOM (explained, no figures); SPY (ETF explained); mobile 390 px (no horizontal overflow); tablet 820 px.

On-screen figures were cross-checked against Apple's 10-K filings (`docs/screenshots/12_tablet_statements.png`):

| | FY2022 | FY2023 | FY2024 | FY2025 |
|---|---|---|---|---|
| Revenue | $394.33B | $383.29B | $391.04B | $416.16B |
| Net income | $99.80B | $97.00B | $93.74B | $112.01B |
| Diluted EPS | $6.11 | $6.13 | $6.08 | $7.46 |

All match the published 10-Ks. Labels carry currency and scale ("USD · billions").

## 3. Clean-room deployment build (Streamlit Community Cloud equivalent)
A fresh venv was created and only `requirements.txt` was installed: **pip install OK (56 s), `pip check`: no broken requirements**. `streamlit run app.py` became healthy in 1.3 s, and Overview, Explorer and Statements rendered with **no secrets configured**. Bundled-snapshot data was clearly labelled with the reason ("SEC requests need a contact e-mail…") and date.

Finding: the very first run in a brand-new venv took >90 s while Python compiled `.pyc` files for Streamlit, pandas and Plotly. Later runs took about 11 s for all three pages. This is a one-time cost per environment.

## 4. Windows executable — `dist/FinancialIntelligenceV7.exe`
Built with PyInstaller 6.22 via `desktop/build_windows.ps1` (onefile, 82 MB; the script runs the tests first and secret-scans the output). Tested on this machine, simulating a **brand-new PC** (empty `LOCALAPPDATA`: no config, cache or lock):

| Test | Result |
|---|---|
| Start (`--no-browser`), health endpoint | healthy in **3.2 s** on port 8501, bound to 127.0.0.1 only; config template created |
| Pages render from the exe (Overview, Explorer, Statements) | PASS |
| Second launch while running | prints "Already running…", exits 0, **no second server** |
| Hard kill (stale lock file left behind), relaunch | stale lock detected, server starts normally |
| Binds to 127.0.0.1 only; free-port search 8501–8599 | yes |
| No secrets in the exe (`AIza…` scan) | clean. The local SEC contact e-mail from `secrets.toml` is also absent, which shows the file was not bundled. |
| Processes left after closing | 0 |

Not tested here: launching by double-click in Explorer with a visible console and a real default browser (the tests ran the same binary from PowerShell with `--no-browser`); SmartScreen behaviour on another PC (the exe is unsigned).

## 5. Security checks
- Configured key absent from rendered pages (AppTest) and from the Gemini request URL (mocked transport).
- Repo, release ZIP and exe scanned for `AIza…` patterns: clean.
- `.streamlit/secrets.toml` exists locally (holds the SEC contact e-mail for testing), is gitignored, and is excluded from the ZIP and the exe.

## 6. Not verified / limitations
- **Live Gemini call with a real key**: not performed, because no key was provided (by design, you were not asked for it). Every Gemini path is tested with mocked HTTP responses. To verify: put your key in `.streamlit/secrets.toml`, open AI Research and click *Generate analysis*.
- **Actual Streamlit Community Cloud deployment**: needs your GitHub and Streamlit accounts. No public URL exists yet. §3 reproduces the install and boot.
- Shared cloud IPs may be throttled by the SEC (HTTP 403). The app then serves the labelled snapshot (53 companies) and explains why.
- Some recent annual reports are in EDGAR but not yet in XBRL Company Facts (TSMC FY2025, Toyota FY2026). The app detects and states this.
