# Changelog

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
