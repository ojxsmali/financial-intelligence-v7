"""Server-side configuration.

Lookup order for every setting: process environment variable, then Streamlit
secrets (``.streamlit/secrets.toml`` locally, the Secrets panel on Streamlit
Community Cloud, or the user-level ``~/.streamlit/secrets.toml``).

Secrets are never returned to the browser by this module. Only booleans such as
``gemini_configured()`` are meant for display.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_DATA_DIR = PROJECT_ROOT / "data"

_EMAIL_RE = re.compile(r"^[^\s@<>()]+@[^\s@<>()]+\.[A-Za-z]{2,}$")


def _streamlit_secret(name: str):
    try:
        import streamlit as st  # local import: keeps core modules usable without Streamlit
    except ImportError:  # pragma: no cover - streamlit is a hard dependency of the app
        return None
    try:
        return st.secrets.get(name)
    except Exception:  # no secrets file present -> StreamlitSecretNotFoundError / FileNotFoundError
        return None


def get_setting(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        value = _streamlit_secret(name)
    if value is None:
        return default
    return str(value).strip()


def get_int_setting(name: str, default: int, *, minimum: int = 0, maximum: int = 10**9) -> int:
    raw = get_setting(name, "")
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def get_bool_setting(name: str, default: bool) -> bool:
    raw = get_setting(name, "").lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def is_valid_email(value: str) -> bool:
    return bool(value) and bool(_EMAIL_RE.match(value.strip())) and len(value) <= 254


def sec_contact_email() -> str:
    """Contact address placed in the SEC User-Agent header (SEC fair-access policy)."""
    email = get_setting("SEC_CONTACT_EMAIL")
    return email if is_valid_email(email) else ""


def gemini_api_key() -> str:
    """Return the Gemini key for server-side use only. Never render or log this value."""
    return get_setting("GEMINI_API_KEY")


def gemini_configured() -> bool:
    key = gemini_api_key()
    return bool(key) and not key.lower().startswith(("paste", "your", "replace", "xxx"))


def cache_dir() -> Path:
    """Writable directory for runtime caches (never inside a PyInstaller bundle)."""
    override = os.environ.get("FIP_CACHE_DIR")
    if override:
        base = Path(override)
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / "FinancialIntelligenceV7"
    elif os.environ.get("XDG_CACHE_HOME"):
        base = Path(os.environ["XDG_CACHE_HOME"]) / "fip-v7"
    else:
        base = Path.home() / ".cache" / "fip-v7"
    base.mkdir(parents=True, exist_ok=True)
    return base
