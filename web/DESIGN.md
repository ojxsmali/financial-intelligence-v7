# Financial Intelligence — web design system

A market terminal for audited fundamentals. The data rules never change: one scale per chart, exact values one click away, direction shown by ▲ ▼ and a sign as well as colour, nothing estimated presented as reported.

## Themes (tokens in `src/styles.css`)

| Token | Terminal (default) | Paper |
|---|---|---|
| `--paper` background | `#06080C` | `#F5F3EE` |
| `--surface` panels | `#0C1016` | `#FBFAF7` |
| `--rule` hairline | `#1D2530` | `#D8D3C8` |
| `--ink` text | `#EAEDF2` | `#16181B` |
| `--muted` | `#828DA0` | `#62656B` |
| `--accent` signal | amber `#FFB224` | burnt amber `#9A5B00` |
| `--accent-2` data | cyan `#2DD4EE` | `#0E7490` |
| `--up` / `--down` | `#3DDC84` / `#FF6B5E` | `#1F6A3A` / `#A2352A` |

Terminal is the default. The masthead toggle switches to Paper and remembers the choice (`localStorage['fip.theme']`); an inline script in `index.html` applies it before first paint.

## Type

- **Space Grotesk** for page, company and section titles.
- **Instrument Sans** for text, with tabular, lining figures.
- **JetBrains Mono** for headline figures, dates, tickers and eyebrows.

## Interaction

| Pattern | Where |
|---|---|
| ⌘K / Ctrl+K / `/` command palette — company search + page jump | everywhere |
| Nav pill slides between pages on a spring (`layoutId`) | masthead |
| KPI tiles: drag and release, they spring back; cursor spotlight; hover lift | KPI strips |
| KPI count-up to the exact reported text | KPI strips |
| Bars grow from zero, lines wipe in, points pop | charts |
| Page settle on navigation; buttons squash on press | everywhere |

Built with `motion`; `<MotionConfig reducedMotion="user">` plus CSS media queries switch it all off for reduced motion.

## Layout

Max width 1240 px. Panels with 18 px radius on a near-black page. KPI strip: 6 → 3 (under 1100 px) → 2 (under 768 px). Checked at 1440, 1280, 768, 390 and 375 px with no horizontal overflow.
