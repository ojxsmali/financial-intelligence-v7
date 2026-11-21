# Financial Intelligence — web design system

Two themes, one grammar. The data rules never change between them: one scale per chart, exact values one click away, direction shown by ▲ ▼ and a sign as well as colour, and nothing estimated presented as reported.

## Themes (tokens in `src/styles.css`)

| Token | Paper (light, research note) | Terminal (dark) |
|---|---|---|
| `--paper` background | `#F5F3EE` | `#0A0E15` |
| `--surface` | `#FBFAF7` | `#0F1520` |
| `--rule` hairline | `#D8D3C8` | `#243044` |
| `--ink` text | `#16181B` | `#E7ECF3` |
| `--muted` | `#62656B` | `#8792A5` (5.8:1) |
| `--accent` | navy `#1D3B5A` | cyan `#5CC8EE` |
| `--accent-2` / `--accent-3` | cyan `#0E7490` / violet `#5B4BB7` | cyan / violet `#A78BFA` |
| `--up` / `--down` | `#1F6A3A` / `#A2352A` | `#45C486` / `#F07A66` |
| Series `--s1…--s6` | blue, orange, green, amber, pink, purple | brighter set, each ≥ 3:1 on the dark surface |

The first visit follows the OS colour scheme; the toggle in the masthead remembers the choice (`localStorage['fip.theme']`). An inline script in `index.html` applies it before first paint, so there is no flash.

## Type

- **Source Serif 4** for page, company and section titles.
- **IBM Plex Sans** with tabular, lining figures for UI and numbers. In Terminal, headline KPI values switch to **IBM Plex Mono**.
- Eyebrows and labels: 0.7 rem, uppercase, 0.08–0.12 em tracking.

## Motion

| Pattern | Where |
|---|---|
| Page settle (8 px rise, 450 ms) | every route change |
| KPI stagger + count-up to the exact reported text | KPI strips |
| KPI hover: cyan→violet top rule draws in | KPI strips |
| Bars grow from the zero line, staggered per fiscal year | column charts |
| Lines wipe in left→right, points pop in | line charts |
| Horizontal bars grow from the axis | Compare, Screener |
| Gradient hairline under the glass masthead | always |

`prefers-reduced-motion: reduce` removes all of it.

## Layout

Max width 1240 px. KPI strip: 6 columns → 3 under 1100 px → 2 under 768 px. Two-column sections collapse under 1100 px. Checked at 1440, 1280, 768, 390 and 375 px in both themes with no horizontal overflow.
