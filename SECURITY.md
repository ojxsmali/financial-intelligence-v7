# Security notes — Financial Intelligence Platform V7

## Secrets
- `GEMINI_API_KEY` and `SEC_CONTACT_EMAIL` are read only server-side. The lookup order is environment variable, then Streamlit secrets, then the desktop `config.toml` (loaded into the process environment by the launcher).
- No page has a key field. The V6 password field for the key has been **removed**.
- The key goes to Google only in the `x-goog-api-key` header, never in a URL.
- `.streamlit/secrets.toml`, `.env` and `secrets*.toml` are gitignored. `scripts/package_release.py` and `desktop/build_windows.ps1` refuse to produce artifacts that contain key-like strings.
- `client.showErrorDetails = "none"`: visitors never see stack traces. Server logs record error *kinds* only, never keys or prompts.

## Abuse protection (AI)
Server-side SQLite quotas: per visitor and per site, per minute, cooldowns. There is also an optional access code with brute-force throttling, a kill switch and a 24 h answer cache. Visitor identity is a salted HMAC of the client IP, and raw IPs are not stored. Forwarded-for headers are ignored unless explicitly trusted. Only free-tier models are allowlisted, so there is no paid fallback.

## Input handling
- Every dynamic string in custom HTML goes through `html.escape`. Raw HTML links are limited to an https allowlist (sec.gov, nasdaqtrader.com, Google AI docs).
- Search input is capped at 80 characters and regex-escaped. Questions are capped at 600 characters and wrapped as data in the prompt, with a system instruction that overrides them.
- CSV upload is limited to 1 MB / 500 rows and parsed as text, then numerically validated. CSV exports neutralise spreadsheet formula injection (`=`, `+`, `-`, `@` prefixes).
- XSRF protection is on. The desktop server binds to `127.0.0.1` only.

## Reporting
If you find a vulnerability, open a private security advisory on the GitHub repository rather than a public issue.
