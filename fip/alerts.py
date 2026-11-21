"""Owner e-mail alerts for unexpected failures, with thresholds, de-duplication and daily caps.

Configuration (server-side environment variables only — never in the browser or the repo):

  ALERT_EMAIL_TO        where alerts go (the owner's address)
  ALERT_EMAIL_FROM      sender shown in the alert (Gmail: the same Gmail address)
  -- option A: Gmail / any SMTP server --
  SMTP_HOST             smtp.gmail.com
  SMTP_PORT             587 (STARTTLS) or 465 (SSL)
  SMTP_USERNAME         the Gmail address
  SMTP_PASSWORD         a Gmail *App Password* (Google Account → Security → 2-Step Verification → App passwords)
  -- option B: Resend HTTP API --
  RESEND_API_KEY        from resend.com (sender domain must be verified there, or use onboarding@resend.dev)

  ALERTS_ENABLED        default true; set false to silence alerts (logging continues)
  ALERT_COOLDOWN_MIN    default 60: the same incident type is e-mailed at most once per this many minutes
  ALERT_DAILY_MAX       default 20: hard cap on alert e-mails per 24 h

If nothing is configured, alerts are skipped and a single "alerts_not_configured" log line is written.
State lives in SQLite under the cache directory. On Vercel that is /tmp, which is per instance, so
two cold instances can each send one copy of the same alert — duplicates stay rare and bounded.
"""
from __future__ import annotations

import json
import smtplib
import sqlite3
import ssl
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

from fip.config import cache_dir, get_bool_setting, get_int_setting, get_setting, is_valid_email

PROJECT = "Financial Intelligence V7"
SERVICES = {"sec": "SEC EDGAR API", "gemini": "Google Gemini API", "backend": "Backend (API server)",
            "frontend": "Web front end", "config": "Server configuration", "email": "Alert e-mail"}
_LOCK = threading.Lock()
_warned_unconfigured = False


def settings() -> dict:
    return {
        "to": get_setting("ALERT_EMAIL_TO"),
        "from": get_setting("ALERT_EMAIL_FROM") or get_setting("SMTP_USERNAME"),
        "smtp_host": get_setting("SMTP_HOST"), "smtp_port": get_int_setting("SMTP_PORT", 587, minimum=1, maximum=65535),
        "smtp_user": get_setting("SMTP_USERNAME"), "smtp_password": get_setting("SMTP_PASSWORD"),
        "resend_key": get_setting("RESEND_API_KEY"),
        "enabled": get_bool_setting("ALERTS_ENABLED", True),
        "cooldown_s": get_int_setting("ALERT_COOLDOWN_MIN", 60, minimum=1, maximum=24 * 60) * 60,
        "daily_max": get_int_setting("ALERT_DAILY_MAX", 20, minimum=1, maximum=500),
    }


def channel(cfg: dict | None = None) -> str:
    cfg = cfg or settings()
    if not cfg["enabled"] or not is_valid_email(cfg["to"]):
        return ""
    if cfg["smtp_host"] and cfg["smtp_user"] and cfg["smtp_password"]:
        return "smtp"
    if cfg["resend_key"] and is_valid_email(cfg["from"] or ""):
        return "resend"
    return ""


class AlertGate:
    """Counts occurrences and decides when an e-mail is warranted."""

    def __init__(self, path: Path | None = None, clock=time.time):
        self.path = Path(path or cache_dir() / "alerts.sqlite3")
        self.clock = clock
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS seen (ts REAL, fp TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS sent (ts REAL, fp TEXT)")

    @contextmanager
    def _db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            yield conn
        finally:
            conn.close()

    def decide(self, fp: str, *, threshold: int, window_s: int, cooldown_s: int, daily_max: int) -> tuple[bool, int, str]:
        """Record one occurrence. Returns (send?, occurrences in window, reason)."""
        now = self.clock()
        with _LOCK, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("DELETE FROM seen WHERE ts < ?", (now - 86400,))
                db.execute("DELETE FROM sent WHERE ts < ?", (now - 86400,))
                db.execute("INSERT INTO seen VALUES (?, ?)", (now, fp))
                count = db.execute("SELECT COUNT(*) FROM seen WHERE fp = ? AND ts >= ?", (fp, now - window_s)).fetchone()[0]
                last = db.execute("SELECT MAX(ts) FROM sent WHERE fp = ?", (fp,)).fetchone()[0]
                sent_today = db.execute("SELECT COUNT(*) FROM sent").fetchone()[0]
                if count < threshold:
                    reason = f"below threshold ({count}/{threshold})"
                elif last is not None and now - last < cooldown_s:
                    reason = "duplicate within cooldown"
                elif sent_today >= daily_max:
                    reason = "daily alert cap reached"
                else:
                    db.execute("INSERT INTO sent VALUES (?, ?)", (now, fp))
                    db.execute("COMMIT")
                    return True, count, "send"
                db.execute("COMMIT")
                return False, count, reason
            except Exception:
                db.execute("ROLLBACK")
                raise


_GATE: AlertGate | None = None


def gate() -> AlertGate:
    global _GATE
    if _GATE is None:
        _GATE = AlertGate()
    return _GATE


def compose(*, category: str, service: str, summary: str, ref: str, severity: str, temporary: bool,
            occurrences: int, window_s: int, detail: str = "", when: datetime | None = None) -> tuple[str, str]:
    when = when or datetime.now(timezone.utc)
    status = "Likely temporary — monitoring" if temporary else "Requires attention"
    subject = f"[{PROJECT}] {severity.upper()}: {category.replace('_', ' ')} — {SERVICES.get(service, service)}"
    lines = [
        f"Project:        {PROJECT}",
        f"Category:       {category}",
        f"Service:        {SERVICES.get(service, service)}",
        f"Severity:       {severity}",
        f"Status:         {status}",
        f"Time (UTC):     {when.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Reference ID:   {ref}",
        f"Occurrences:    {occurrences} in the last {max(1, window_s // 60)} min",
        "",
        f"What happened:  {summary}",
    ]
    if detail:
        lines.append(f"Technical note: {detail}")
    lines += ["", "Full details: Vercel → financial-intelligence-v7 → Logs, search for the reference ID.",
              "Visitors saw a friendly message only; no technical details were shown to them.",
              "", "Repeats of this incident type are suppressed for the cooldown period."]
    return subject, "\n".join(lines)


def _send_smtp(cfg: dict, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, cfg["from"] or cfg["smtp_user"], cfg["to"]
    msg.set_content(body)
    context = ssl.create_default_context()
    if cfg["smtp_port"] == 465:
        with smtplib.SMTP_SSL(cfg["smtp_host"], 465, timeout=8, context=context) as s:
            s.login(cfg["smtp_user"], cfg["smtp_password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=8) as s:
            s.starttls(context=context)
            s.login(cfg["smtp_user"], cfg["smtp_password"])
            s.send_message(msg)


def _send_resend(cfg: dict, subject: str, body: str) -> None:
    r = requests.post("https://api.resend.com/emails", timeout=8,
                      headers={"Authorization": f"Bearer {cfg['resend_key']}", "Content-Type": "application/json"},
                      data=json.dumps({"from": cfg["from"], "to": [cfg["to"]], "subject": subject, "text": body}))
    if r.status_code >= 300:
        raise RuntimeError(f"Resend returned HTTP {r.status_code}")


def deliver(subject: str, body: str, cfg: dict | None = None) -> str:
    """Send one e-mail now. Returns the channel used. Raises on failure (callers log, never re-raise)."""
    cfg = cfg or settings()
    ch = channel(cfg)
    if ch == "smtp":
        _send_smtp(cfg, subject, body)
    elif ch == "resend":
        _send_resend(cfg, subject, body)
    else:
        raise RuntimeError("alerts not configured")
    return ch


def maybe_alert(*, category: str, service: str, summary: str, ref: str, severity: str = "error", temporary: bool = True,
                threshold: int = 1, window_s: int = 600, fingerprint: str = "", detail: str = "") -> str:
    """Returns 'sent', 'suppressed: <reason>', 'not configured' or 'failed'."""
    from fip.observability import log_event
    global _warned_unconfigured
    cfg = settings()
    if not channel(cfg):
        if not _warned_unconfigured:
            _warned_unconfigured = True
            log_event("warning", "alerts_not_configured",
                      hint="Set ALERT_EMAIL_TO plus SMTP_* or RESEND_API_KEY to receive e-mail alerts.")
        return "not configured"
    send, count, reason = gate().decide(fingerprint or f"{category}:{service}", threshold=threshold, window_s=window_s,
                                        cooldown_s=cfg["cooldown_s"], daily_max=cfg["daily_max"])
    if not send:
        log_event("info", "alert_suppressed", category=category, reason=reason, ref=ref)
        return f"suppressed: {reason}"
    subject, body = compose(category=category, service=service, summary=summary, ref=ref, severity=severity,
                            temporary=temporary, occurrences=count, window_s=window_s, detail=detail)
    try:
        ch = deliver(subject, body, cfg)
        log_event("info", "alert_sent", category=category, channel=ch, ref=ref)
        return "sent"
    except Exception as exc:
        log_event("error", "alert_delivery_failed", category=category, error_type=type(exc).__name__, ref=ref)
        return "failed"
