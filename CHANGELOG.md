# Changelog

## 7.5.0 — 2026-11-21 · Terminal theme and motion

- Second theme, "Terminal": blue-black glass, cyan accent with a violet second voice, mono KPI figures. The first visit follows the OS; the masthead toggle remembers the choice, applied before first paint.
- Chart series colours moved to theme tokens, each set colour-blind validated and ≥ 3:1 on its surface.
- Motion with a purpose: KPI count-up to the exact reported text, bars growing from the zero line, lines wiping in, page settle on navigation, KPI hover rule. All of it is off for reduced motion.
- Glass masthead with a cyan→violet hairline; duplicated control styles removed from `styles.css`.
- `web/DESIGN.md` documents both themes. 212 Python tests, 26 web tests.

## 7.4.0 — 2026-11-21 · Production error handling, monitoring and alerts

- Visitors never see internal errors: safe, consistent messages with a reference ID; specific validation messages kept.
- Request IDs on every API response; structured, secret-scrubbed JSON logs (Vercel Runtime Logs).
- Owner e-mail alerts (Gmail SMTP or Resend) with thresholds, hourly de-duplication and a daily cap.
- Serverless time budgets for SEC and Gemini calls; front-end request timeouts, error boundary and crash reporting.
- Tests for ten failure scenarios (SEC down / refusing, Gemini down / invalid / network / timeout / key rejected, missing configuration, invalid input, unavailable dataset, unexpected exception) and the alert engine. 209 Python tests, 21 web tests.

## 7.3.0 — 2026-11-21 · Watchlist, screener, health check, plain English

- **Watchlist + live filings feed**: follow companies; every SEC filing is explained in plain English (8-K item numbers decoded: earnings, executive changes, deals, restatements, cyber incidents) with "New since last visit" badges. Auto-refreshes.
- **Market screener** over all SEC filers via XBRL frames, with every displayed row verified against the company's own annual report. Found and handled real SEC data errors (a quarter tagged as a full year; impossible margins). Never mixes currencies.
- **Financial health check**: Piotroski F-score (9 tests) with plain-language questions, numbers and "why it matters"; skipped tests never count as failures. Extraction adds current assets/liabilities, long-term debt and diluted share count.
- **Plain-English insights**: every observation says how it was worked out and where the numbers come from; formulas tucked behind "Formula".
- **Auto-update**: financials refresh as soon as a newer annual report appears on EDGAR; versioned cache; daily listings refresh commits under the owner's name.
- **Fixes from stress testing**: `BRK-B`-style tickers resolve; consistent friendly API errors (422/404); empty symbol search; "Re-check SEC" throttled (10 min per company) so the site can't be used to hammer SEC; screener returns a clear 503 when SEC is unreachable; leftover CSS overriding segmented controls; compact mobile toolbar.
- Tests: 190 Python, 16 web.

## 7.2.0 — 2026-11-21 · Web app on Vercel

- **New web front end** (`web/`): React 19 + TypeScript + Vite, same "research note" design system, all seven pages (Overview, Explorer, Compare, Statements, Insights with CSV upload, Assistant, Sources). Selected company is in the URL (`?t=AAPL`).
- **JSON API** (`fip/api.py`, FastAPI) over the unchanged data engine; deployed on Vercel as a Python function (`api/index.py`, `vercel.json`). Edge caching for company/compare/search responses; caches in `/tmp` on Vercel.
- Accessibility: ARIA combobox for company search, WAI-ARIA tabs, radio-group segmented controls, keyboard-focusable chart years with tooltips, data tables for every chart, skip link, focus moved to the page on navigation.
- Fix (shared core): concurrent cache writes for the same company could crash on Windows (shared `.tmp` file); writes now use unique temp files and never fail a request.
- Dependencies split: `requirements.txt` (core + API, what Vercel installs), `requirements-streamlit.txt`, `requirements-dev.txt`. CI gains a web job (tests + build).
- Tests: 171 Python (11 new API tests), 12 web.

## 7.1.0 — 2026-11-20 · UI redesign

- **New design system** ("research note"): light paper/ink theme with one navy accent, Source Serif 4 + IBM Plex Sans/Mono, tabular figures, hairline structure instead of cards. Tokens in `fip/ui/theme.py`, mirrored in `.streamlit/config.toml`.
- **Charts rebuilt without Plotly** (`fip/ui/charts.py`): server-rendered HTML/SVG, one stated scale, straight segments (no spline smoothing), legends, keyboard-focusable per-year tooltips, and a data-table alternative. Colour-blind-validated 6-colour palette in fixed order; on Compare each company keeps its colour across charts. Plotly removed from requirements and the exe.
- Company masthead, KPI strip and balance-sheet strip replace gradient banner and coloured cards; deltas use ▲/▼ plus sign, never colour alone.
- Mobile: page links stay one tap away (Streamlit folds its top nav into the drawer on phones); verified at 320, 360, 820 and 1440 px with no horizontal page overflow.
- Accessible tables (row/column headers, scrollable regions), visible focus rings, reduced-motion support, live loading status.
- Honest labelling: rule-based insights say "not AI-generated"; the Assistant page is the only AI feature and names Gemini. Page icons and emoji removed.
- Fixes: fiscal year-end shown as "26 Sep" (was "Sep 26", readable as a year); Compare uses listing names instead of SEC's upper-case names; "1 match" grammar; explorer grid no longer clips its last row; disabled primary button readable.
- Optional `.env` loading (`.env.example` added; real environment variables win). Credit: "Designed & built by Ojas Mali".
- Tests: 158 (new chart, `.env` and fiscal-year-end tests).

## 7.0.0 — 2026-11-03

### Company coverage
- **Replaced the 6 hardcoded companies with a dynamic universe** of every US exchange-listed security (13,239 at build time; 5,608 operating companies; 7,630 with an SEC CIK). It merges Nasdaq Trader directories with SEC's ticker→CIK file, refreshes every 24 h, and falls back to a bundled snapshot when the network is unavailable.
- Instrument classification separates common stock and ADRs from ETFs, ETNs, closed-end funds, preferreds, warrants, units, rights and notes. ETFs that have an SEC CIK are never treated as operating companies.
- Ticker normalisation handles `BRK.B` / `BRK-B` / `brkb`, preferred (`BAC$K` ↔ `BAC-PK`), units, warrants and rights. Share classes that share one registrant are linked (GOOG/GOOGL, BRK.A/BRK.B).
- Delisting handling: tickers that SEC still lists but that are missing from today's exchange directories are excluded. Nasdaq test issues and OTC tickers are excluded.
- Sector, country and fiscal year-end per registrant come from SEC submissions (SIC codes).

### Financial correctness (V6 bugs fixed)
- **Units:** V6 displayed bare numbers (USD millions) without labels. V7 stores full units and formats every value with currency and scale (`$416.16B`, `40.31%`, `+1.2 pp`), with a global unit selector.
- **Fiscal-year labels:** V6 used the calendar year of the period end. V7 uses the filer's own fiscal year (e.g. Walmart FY2025 ends Jan 2025) and shows period dates and filing dates separately.
- **Revenue concept:** V6 used a single concept for all years. That under-stated insurers and banks (contract revenue only) and broke when filers switched concepts. V7 takes the total-revenue concept per year and records it.
- **Duplicate-year crash:** V6's `prepare_data` raised "Duplicate ticker/year" when a 52/53-week year produced two period ends in one calendar year. V7 periods are keyed by period end.
- Added 20-F/40-F support, IFRS (`ifrs-full`) and non-USD reporting currencies. USD convenience translations are not used.
- Restatements are detected and flagged. Fiscal year-end changes, gaps and stale structured data are warned about.
- New metrics: gross, operating and FCF margins, operating income, assets, liabilities, equity, cash, operating cash flow, capex, free cash flow (derived, disclosed), diluted EPS, ROE, cash conversion, CAGR.
- Growth is computed only between consecutive fiscal years and only from a positive base.
- The app explains registrants without annual data (e.g. ExxonMobil Holdings, 10-Q only) and never substitutes other data.

### Data engineering
- SEC client with contact User-Agent, a 5 req/s process-wide limiter, timeouts, and exponential backoff with `Retry-After`. Typed 403/404/429/5xx errors.
- Two-level caching (memory + disk: 12 h financials, 24 h profiles and listings), with visible stale-cache and snapshot fallbacks. Retrieval timestamps appear on every page.
- A bundled snapshot of 53 large companies, plus GitHub Actions to refresh listings, profiles and snapshots on weekdays.

### UI/UX
- Full redesign: navy/charcoal theme with emerald, cyan and amber accents, Inter and JetBrains Mono, design tokens, KPI cards with tooltips and deltas, skeleton loaders, empty and error states, provenance chips, shared-scale Plotly charts, and responsive layouts at 390/820/1440 px.
- Seven pages: Overview, Explorer, Compare, Statements, Insights, AI Research, Sources.
- Explorer with ranked search, filters, pagination and row actions. Compare supports up to 6 companies.

### AI (Gemini)
- **Removed the public API-key input field.** The key is server-side only, sent in a header, and never rendered or logged.
- Free-tier allowlist (`gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-2.5-flash-lite`; `gemini-3.6-flash` optional). Models outside the list are rejected.
  - V6's `gemini-3.1-flash-lite` stays in the chain; it has a shutdown date of May 2027.
  - Fallback happens on 404/429/5xx, with one retry on 5xx. Auth errors stop immediately.
- Structured fact pack (SEC values, ratios, periods, accession numbers) and a system instruction requiring separate facts, calculations, hypotheses and limitations with fiscal-year citations.
- Server-side abuse protection replaces the browser-session counter (bypassed by a page reload in V6). See SECURITY.md.

### Launch & packaging
- **One-click Windows executable** (PyInstaller onefile): free-port selection, single-instance lock, auto browser open, clean shutdown, troubleshooting output and a log file. No Python, no ZIP, no BAT files.
- Streamlit Community Cloud configuration and a clean-room install check. CI, data-refresh and Windows-build GitHub workflows.

### Quality
- 142 automated tests (up from V6's 9), including real-filing regressions and headless rendering of all pages, plus a Playwright browser E2E check with screenshots.
- CSV import accepts V6's `year,revenue,net_income` format plus optional columns, with a declared unit scale, size limits and validation. Exports include units and provenance and are formula-injection safe.
