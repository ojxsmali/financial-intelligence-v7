# Financial Intelligence V7 — code & UX review (2026-11-20)

Reviewed before the UI redesign. Everything below was read in the code or seen in the running app
(Streamlit 1.65, Python 3.10, live SEC data, desktop 1440 px and phone 360 px).

## What it is
A Streamlit research app over **SEC EDGAR XBRL Company Facts**: a searchable universe of ~13,000 US-listed
securities (Nasdaq Trader directories + SEC ticker→CIK map), audited annual statements for ~5,600 operating
companies, derived ratios, rule-based insights, a CSV analyzer, and a **Gemini** research assistant restricted to
free-tier models. It ships as a Streamlit Cloud app and a one-file Windows exe (`desktop/launcher.py` + PyInstaller).

## Architecture & data flow
```
Nasdaq Trader + SEC tickers ──► fip.universe ──► universe.csv (24 h refresh, bundled fallback)
SEC companyfacts JSON ──► fip.http_client (UA + 5 req/s limiter + retry/backoff)
                       ──► fip.xbrl (annual-only facts, FY labels, restatements, derived metrics)
                       ──► fip.data_service (disk cache 12 h → live → stale cache → bundled snapshot)
                       ──► fip.metrics / fip.insights (ratios, growth, CAGR, rule-based observations)
                       ──► fip.gemini (bounded "fact pack" in millions + question → free-tier model chain)
                            guarded by fip.ai_guard (SQLite: per-visitor/global caps, cooldown, answer cache)
fip.ui + views/*  ──► Streamlit pages (state, sidebar, components, charts)
```
The `fip` core is UI-agnostic and testable without Streamlit — the best decision in the codebase.

## Code quality — good
- Typed errors with user-safe messages; nothing from other companies is ever substituted.
- Correct financial hygiene: annual-only facts, 350–380-day duration check, consecutive-year growth only,
  one scale per chart/table, full units in CSV exports, formula-injection neutralised.
- **144 tests pass, 1 skipped** (the git-tracking test — this folder is not a git checkout).

## Security — no problems found
- `GEMINI_API_KEY` is read server-side only, sent in the `x-goog-api-key` header (never a URL), never rendered;
  tests assert this. Error text uses status codes/enum reasons, never response bodies.
- Local `.streamlit/secrets.toml` holds only `SEC_CONTACT_EMAIL` (no Gemini key) and is gitignored, as are `.env*`.
- Release zip checked: contains only `secrets.toml.example`. The exe spec bundles `config.toml`, never secrets.
- `showErrorDetails = "none"`, XSRF on, `X-Forwarded-For` only trusted when explicitly enabled, access code
  compared in constant time with brute-force throttling.

## Bugs & rough edges
1. **Not a git repository and no remote** — nothing for this project on GitHub yet from this folder.
2. **Margin and trend lines used spline smoothing** between annual points — implies intra-year data that does
   not exist. Dishonest-looking for a finance product.
3. **Charts have no table alternative and no screen-reader text**; Plotly hover is mouse-only. The series palette
   (emerald/cyan/amber/violet/pink/blue on navy) was not checked for colour-blind separation (emerald vs cyan vs blue).
4. Compare table mixes listing names with SEC's upper-case entity names ("Apple Inc." next to "MICROSOFT CORP").
5. Fiscal year-end shown as "Sep 25" — reads like a year (September 2025), not a day.
6. Browser tab shows "Streamlit" while each page loads; favicon is an emoji; the AI page uses a sparkle icon.
7. On phones all seven pages hide behind the sidebar drawer, and the company picker sits in the same drawer —
   the two most-used controls need two taps each.
8. Four 404s in the console on every load (Streamlit-internal asset requests; harmless but noisy).

## Performance
- Plotly ships ~3.5 MB of JS and re-renders on every rerun; a page with 4 charts is the slowest part of the app.
- Universe (2.7 MB CSV) is cached per process; company bundles cached 30 min and loaded concurrently on Compare.
- Every widget interaction reruns the full page script (Streamlit model) — acceptable for this data size.

## UX / visual
Default "dark dashboard" look: navy background with radial glows, gradient company banner, gradient logo tile,
coloured left-border KPI cards, everything inside a bordered card, Inter + JetBrains Mono for figures. Competent
but generic; it reads as a template rather than a research product. Hierarchy is flat — the KPI strip, charts,
insights and balance sheet all have the same visual weight.

## Decision for the redesign: stay in Streamlit, replace the presentation layer
Recommended and implemented. Reasons:
- The working parts that matter — the server-side key model, AI guard, Streamlit Cloud deploy path, the one-file
  exe, and the AppTest page suite — all depend on Streamlit. A separate web frontend would need a new API layer,
  a new host for the Python backend, and a rewritten launcher; high risk to "keep every function working".
- What made the old UI weak was not Streamlit itself but Plotly defaults and card-everything CSS. Both are
  replaceable: charts are now server-rendered **accessible SVG** (with legend, `<title>` per mark, and a
  data-table alternative), and the theme is a token-based light "research paper" system.
- Trade-off accepted: Streamlit still controls widget internals (select boxes, data grid) and reruns, so some
  styling targets Streamlit's `data-testid` hooks; versions are pinned `<2.0` for that reason.

## Status after the redesign (7.1.0)
Fixed: 2 (straight segments), 3 (legend + keyboard tooltips + data tables + validated palette), 4, 5 ("26 Sep"),
6 (Material favicon, no emoji/sparkle icons), 7 (mobile page row). Still open: 1 (not a git repo — needs the owner's
go-ahead to init and push), 8 (the 404s are Streamlit probing `/<page>/_stcore/health` on sub-page URLs; harmless).
Verified: 158 tests pass; Playwright e2e 27/27 on live SEC data (screenshots in `docs/screenshots/`).
The prebuilt `release/FinancialIntelligenceV7.exe` predates the redesign — rebuild with `desktop/build_windows.ps1`.
