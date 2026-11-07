# Bundled data snapshots

The app is the primary data source. It refreshes listings every 24 h and filings every 12 h. The files here are only the **fallback** for when the network is down or the SEC blocks a host. The UI always labels snapshot data and shows its date.

| File | Content | Built by |
|---|---|---|
| `universe.csv`, `universe_meta.json` | Every US exchange-listed security with type, exchange, CIK, sector and country | `scripts/refresh_universe.py` |
| `sec_profiles.csv` | SIC code, country and fiscal year-end per SEC registrant | `scripts/build_sec_profiles.py` (incremental) |
| `financials_snapshot/CIK##########.json` | Extracted annual statements for 53 widely followed companies | `scripts/refresh_financials_snapshot.py` |

All content is public SEC / Nasdaq Trader data. `.github/workflows/refresh-data.yml` refreshes it on weekdays.
