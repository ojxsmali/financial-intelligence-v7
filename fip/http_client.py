"""Polite HTTP access to SEC EDGAR and the Nasdaq Trader symbol directory.

* Identifies itself with a User-Agent that includes a contact e-mail, as the
  SEC fair-access policy requires (https://www.sec.gov/os/accessing-edgar-data).
* Process-wide rate limit well under the SEC ceiling of 10 requests/second.
* Timeouts, bounded retries with exponential backoff + jitter for 429/5xx,
  ``Retry-After`` support, and typed errors so the UI can explain failures.
"""
from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

import requests

from fip import VERSION
from fip.config import sec_contact_email

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_TIMEOUT = (6, 40)  # (connect, read) seconds
MAX_ATTEMPTS = 4
MAX_BACKOFF_SECONDS = 12.0


class DataSourceError(RuntimeError):
    """Base class. ``user_message`` is safe to display; it never contains secrets."""

    def __init__(self, user_message: str, *, status: int | None = None, url: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.status = status
        self.url = url


class ConfigurationError(DataSourceError):
    pass


class NotFoundError(DataSourceError):
    pass


class AccessDeniedError(DataSourceError):
    pass


class RateLimitedError(DataSourceError):
    pass


class UpstreamUnavailableError(DataSourceError):
    pass


class RateLimiter:
    """Thread-safe minimum-interval limiter shared by every request in the process."""

    def __init__(self, max_per_second: float):
        self.interval = 1.0 / max_per_second
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.interval
        delay = slot - now
        if delay > 0:
            time.sleep(delay)


SEC_LIMITER = RateLimiter(max_per_second=5.0)
OTHER_LIMITER = RateLimiter(max_per_second=2.0)

_session_local = threading.local()


def _session() -> requests.Session:
    sess = getattr(_session_local, "session", None)
    if sess is None:
        sess = requests.Session()
        _session_local.session = sess
    return sess


def sec_user_agent(contact_email: str | None = None) -> str:
    email = (contact_email or sec_contact_email()).strip()
    if not email:
        raise ConfigurationError(
            "SEC requests need a contact e-mail in the User-Agent header. "
            "Set SEC_CONTACT_EMAIL in Streamlit secrets or the environment, or enter one under Settings."
        )
    return f"FinancialIntelligencePlatform/{VERSION} ({email})"


def _retry_after_seconds(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError):
            return None


def _backoff(attempt: int) -> float:
    return min(MAX_BACKOFF_SECONDS, (2 ** attempt) * 0.75 + random.uniform(0, 0.5))


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes
    fetched_at: float


def fetch(url: str, *, sec: bool, contact_email: str | None = None,
          timeout=DEFAULT_TIMEOUT, transport=None, sleep=time.sleep) -> FetchResult:
    """GET ``url`` with retries. ``transport`` and ``sleep`` are injectable for tests."""
    if transport is None and os.environ.get("FIP_OFFLINE") == "1":
        raise UpstreamUnavailableError("Offline mode (FIP_OFFLINE=1): network requests are disabled.", url=url)
    headers = {"Accept-Encoding": "gzip, deflate"}
    if sec:
        headers["User-Agent"] = sec_user_agent(contact_email)
    else:
        headers["User-Agent"] = f"FinancialIntelligencePlatform/{VERSION}"
    limiter = SEC_LIMITER if sec else OTHER_LIMITER
    get = transport or _session().get
    source = "SEC EDGAR" if sec else "the symbol directory"

    last_status = None
    for attempt in range(MAX_ATTEMPTS):
        limiter.wait()
        try:
            response = get(url, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last_status = None
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_backoff(attempt))
                continue
            raise UpstreamUnavailableError(
                f"Could not reach {source} ({type(exc).__name__}). Check the network connection.", url=url
            ) from None

        status = response.status_code
        last_status = status
        if status == 200:
            return FetchResult(url=url, status=status, content=response.content, fetched_at=time.time())
        if status == 404:
            raise NotFoundError(f"{source} has no document at this address (HTTP 404).", status=404, url=url)
        if status in (401, 403):
            raise AccessDeniedError(
                f"{source} refused the request (HTTP {status}). SEC blocks requests without a valid "
                "contact User-Agent and may temporarily block shared cloud IP ranges that exceed fair-access limits.",
                status=status, url=url,
            )
        if status in RETRYABLE_STATUS and attempt + 1 < MAX_ATTEMPTS:
            wait = _retry_after_seconds(response)
            sleep(min(MAX_BACKOFF_SECONDS, wait) if wait is not None else _backoff(attempt))
            continue
        if status == 429:
            raise RateLimitedError(f"{source} rate limit reached (HTTP 429). Try again in a minute.", status=429, url=url)
        if status in RETRYABLE_STATUS:
            raise UpstreamUnavailableError(
                f"{source} is temporarily unavailable (HTTP {status}) after {MAX_ATTEMPTS} attempts.", status=status, url=url
            )
        raise DataSourceError(f"{source} returned unexpected HTTP {status}.", status=status, url=url)

    raise UpstreamUnavailableError(f"{source} request failed (last status {last_status}).", status=last_status, url=url)
