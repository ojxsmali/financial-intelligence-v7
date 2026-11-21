"""Private error monitoring: request references, structured logs and owner alerts.

* Every API request gets a reference ID (``FI-7K3Q9A``) returned in the ``X-Request-ID`` header and in
  every error body, so a visitor can quote it and the owner can find the matching log line.
* Logs are one JSON object per line on stdout/stderr — on Vercel they appear in the project's
  Function **Runtime Logs** (searchable by reference ID). Locally they go to the console.
* Logs are scrubbed: values of keys that look like secrets are dropped, and API keys, bearer tokens
  and e-mail addresses are masked wherever they appear in text.
* ``report()`` records an incident and asks ``fip.alerts`` whether it deserves an e-mail
  (thresholds, de-duplication and daily caps live there).
"""
from __future__ import annotations

import contextvars
import json
import logging
import re
import secrets
import sys
import time
import traceback
from datetime import datetime, timezone

PROJECT = "Financial Intelligence V7"
_ref: contextvars.ContextVar[str] = contextvars.ContextVar("fip_request_ref", default="")

_logger = logging.getLogger("fip.monitor")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

SENSITIVE_KEY = re.compile(r"key|token|secret|password|passwd|authorization|cookie|access_code|credential|smtp_pass",
                           re.IGNORECASE)
_MASKS = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "[redacted-key]"),
    (re.compile(r"\bre_[0-9A-Za-z_]{16,}"), "[redacted-key]"),
    (re.compile(r"(?i)bearer\s+[0-9a-z._\-]+"), "Bearer [redacted]"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"(?i)(x-goog-api-key|api[_-]?key|password|token)(['\"]?\s*[:=]\s*)['\"]?[^\s'\",}]+"), r"\1\2[redacted]"),
]


def new_ref() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"        # no 0/O/1/I confusion when read aloud
    return "FI-" + "".join(secrets.choice(alphabet) for _ in range(6))


def set_ref(ref: str) -> contextvars.Token:
    return _ref.set(ref)


def reset_ref(token: contextvars.Token) -> None:
    _ref.reset(token)


def current_ref() -> str:
    return _ref.get() or new_ref()


def scrub(value, depth: int = 0):
    """Remove secrets from anything we are about to log or e-mail."""
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        return {k: ("[redacted]" if SENSITIVE_KEY.search(str(k)) else scrub(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v, depth + 1) for v in list(value)[:20]]
    if isinstance(value, str):
        text = value
        for pattern, repl in _MASKS:
            text = pattern.sub(repl, text)
        return text[:2000]
    return value


def log_event(level: str, event: str, **fields) -> dict:
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "level": level.upper(),
              "project": PROJECT, "event": event, "ref": fields.pop("ref", None) or _ref.get() or None}
    record.update(scrub(fields))
    line = json.dumps(record, default=str, separators=(",", ":"))
    getattr(_logger, level.lower() if level.lower() in ("info", "warning", "error", "critical") else "info")(line)
    return record


def exception_summary(exc: BaseException) -> dict:
    """Type, short message and the last few frames (file:line function) — never local variables."""
    frames = traceback.extract_tb(exc.__traceback__)[-6:] if exc.__traceback__ else []
    return {"error_type": type(exc).__name__, "error_message": str(exc)[:400],
            "where": [f"{f.filename.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]}:{f.lineno} {f.name}" for f in frames]}


def report(category: str, service: str, summary: str, *, exc: BaseException | None = None, severity: str = "error",
           temporary: bool = True, threshold: int = 1, window_s: int = 600, fingerprint: str = "", **fields) -> dict:
    """Record an incident privately and, when it qualifies, e-mail the owner.

    category: sec_outage | gemini_outage | gemini_auth | gemini_quota | config | internal | frontend | ...
    severity: info | warning | error | critical.   temporary=False means "requires attention".
    threshold/window_s: alert only after `threshold` occurrences within `window_s` seconds.
    """
    details = exception_summary(exc) if exc is not None else {}
    record = log_event("error" if severity in ("error", "critical") else "warning", "incident", category=category,
                       service=service, severity=severity, temporary=temporary, summary=summary, **details, **fields)
    try:
        from fip import alerts
        alerts.maybe_alert(category=category, service=service, summary=scrub(summary), ref=record["ref"] or new_ref(),
                           severity=severity, temporary=temporary, threshold=threshold, window_s=window_s,
                           fingerprint=fingerprint or f"{category}:{service}",
                           detail=scrub(details.get("error_type", "") + (": " + details["error_message"]
                                                                        if details.get("error_message") else "")))
    except Exception as alert_exc:  # monitoring must never break the request it is monitoring
        log_event("warning", "alert_failed", error_type=type(alert_exc).__name__)
    return record


class Timer:
    def __init__(self):
        self.start = time.perf_counter()

    @property
    def ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)
