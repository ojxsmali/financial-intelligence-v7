"""Production error handling: the 10 failure scenarios, private logging and owner alerts.

For every scenario the visitor must get a calm message with a reference ID and no internals,
while the incident is logged privately and (when it qualifies) e-mailed to the owner.
"""
import json
import re

import pytest
import requests
from fastapi.testclient import TestClient

SECRET = "AIza" + "UnitTestSecretValueThatMustNeverRender01"
LEAKS = re.compile(r"Traceback|HTTP \d{3}|GEMINI_API_KEY|SEC_CONTACT_EMAIL|FIP_OFFLINE|Offline mode|\.py\b|"
                   r"Exception|KeyError|NameError|x-goog|10-Q \(\d+\)|XBRL", re.IGNORECASE)


@pytest.fixture()
def alerts(monkeypatch):
    """Alerts configured with a fake delivery that records instead of sending."""
    import fip.alerts as al
    sent = []
    monkeypatch.setenv("ALERT_EMAIL_TO", "owner@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password-123")
    monkeypatch.setattr(al, "_GATE", None)
    monkeypatch.setattr(al, "deliver", lambda subject, body, cfg=None: sent.append((subject, body)) or "smtp")
    return sent


@pytest.fixture()
def client(monkeypatch):
    import fip.api
    fip.api._UNIVERSE = None
    fip.api._GUARD = None
    return TestClient(fip.api.app, raise_server_exceptions=False)


def visitor_safe(resp):
    """Visitor-facing text (errors, caveats, feed status) must carry no internals; data fields may
    legitimately mention XBRL concepts or SEC URLs, so only the message fields are checked for leaks."""
    body = resp.json()
    assert SECRET not in resp.text and "app-password" not in resp.text and "Traceback" not in resp.text
    shown = [json.dumps(body.get("error", "")), json.dumps(body.get("notices", [])), str(body.get("events_error", "")),
             str(body.get("profile_error", ""))]
    for text in shown:
        assert not LEAKS.search(text), LEAKS.search(text).group(0)
    return body


@pytest.fixture()
def log_lines():
    import logging
    import fip.observability as ob
    lines = []

    class Grab(logging.Handler):
        def emit(self, record):
            lines.append(json.loads(record.getMessage()))
    h = Grab()
    ob._logger.addHandler(h)
    yield lines
    ob._logger.removeHandler(h)


def categories(sent):
    return [s.split("]", 1)[1] for s, _ in sent]


# 1. SEC API unavailable (no network, nothing cached) -------------------------------------------
def test_sec_unavailable(client, alerts):
    for _ in range(3):                                  # threshold 3 → one alert
        body = visitor_safe(client.get("/api/company/ETSY"))
    assert body["status"] == "error" and body["error"]["retryable"] is True
    assert body["error"]["message"] == "Financial data is temporarily unavailable. Please try again later."
    assert len(alerts) == 1 and "sec outage" in alerts[0][0] and "SEC EDGAR API" in alerts[0][0]


# 2. SEC returns an unsuccessful response ---------------------------------------------------------
def test_sec_unsuccessful_response(client, alerts, monkeypatch):
    from fip import data_service
    from fip.http_client import AccessDeniedError
    def refuse(url, **kw):
        raise AccessDeniedError("SEC EDGAR refused the request (HTTP 403).", status=403)
    monkeypatch.setattr(data_service, "fetch", refuse)
    monkeypatch.setattr(data_service.load_financials, "__defaults__", (False, None, refuse))
    body = visitor_safe(client.get("/api/company/AAPL"))       # bundled snapshot covers AAPL
    assert body["status"] == "ok"
    assert body["notices"] and "saved snapshot" in body["notices"][0]


# 3. Gemini unavailable / 4. invalid response / 5. network failure / 6. timeout ------------------
class _Resp:
    def __init__(self, status, payload=None, bad_json=False):
        self.status_code, self._payload, self._bad = status, payload, bad_json
        self.ok = status < 300

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._payload


@pytest.mark.parametrize("behaviour,status,expected", [
    ("down", 503, "The research assistant is temporarily unavailable. Please try again shortly."),
    ("invalid", 400, "Gemini returned no text. Try a more specific question."),
    ("network", 503, "The research assistant is temporarily unavailable. Please try again shortly."),
    ("timeout", 503, "The research assistant is temporarily unavailable. Please try again shortly."),
    ("auth", 503, "This service is temporarily unavailable. We are working to restore it."),
])
def test_gemini_failures(client, alerts, monkeypatch, behaviour, status, expected):
    import fip.gemini
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setenv("AI_COOLDOWN_SECONDS", "0")

    def post(url, **kw):
        if behaviour == "down":
            return _Resp(503, {"error": {"status": "UNAVAILABLE"}})
        if behaviour == "invalid":
            return _Resp(200, bad_json=True)
        if behaviour == "network":
            raise requests.ConnectionError("dns failure for generativelanguage.googleapis.com")
        if behaviour == "timeout":
            raise requests.Timeout("read timed out")
        return _Resp(403, {"error": {"status": "PERMISSION_DENIED", "details": [{"reason": "API_KEY_INVALID"}]}})
    monkeypatch.setattr(fip.gemini.requests, "post", post)
    monkeypatch.setattr(fip.gemini.time, "sleep", lambda s: None)
    r = client.post("/api/assistant/ask", json={"symbols": ["AAPL"], "question": f"Revenue trend? {behaviour}"})
    body = visitor_safe(r)
    assert r.status_code == status and body["error"]["message"] == expected
    assert body["error"]["ref"].startswith("FI-")
    if behaviour == "auth":
        assert any("gemini auth" in c for c in categories(alerts))
        assert "Requires attention" in alerts[-1][1]


def test_gemini_respects_time_budget():
    from fip.gemini import GeminiError, generate
    clock = iter([0, 0, 100, 100, 100])
    with pytest.raises(GeminiError) as e:
        generate({"companies": []}, "q", "key", models=["gemini-3.5-flash-lite", "gemini-2.5-flash-lite"],
                 transport=lambda url, **kw: _Resp(503, {"error": {"status": "UNAVAILABLE"}}),
                 sleep=lambda s: None, deadline=40, clock=lambda: next(clock))
    assert e.value.kind == "unavailable"


# 7. Required environment variable missing ---------------------------------------------------------
def test_missing_configuration(client, alerts, monkeypatch):
    import fip.http_client
    monkeypatch.delenv("FIP_OFFLINE")
    monkeypatch.setattr(fip.http_client, "_session", lambda: pytest.fail("must not call SEC without a contact"))
    body = visitor_safe(client.get("/api/company/ETSY"))
    assert body["error"]["message"] == "Financial data is temporarily unavailable. Please try again later."
    assert any("config" in c for c in categories(alerts))
    ask = visitor_safe(client.post("/api/assistant/ask", json={"symbols": ["AAPL"], "question": "q"}))
    assert ask["error"]["kind"] == "not_configured"                       # GEMINI_API_KEY not set
    assert "isn't available on this site right now" in ask["error"]["message"]


# 8. Invalid user input keeps useful, specific feedback ----------------------------------------------
def test_validation_messages_stay_helpful(client, alerts, monkeypatch):
    r = client.post("/api/upload", json={"csv_text": "fiscal_year,revenue\n2024,1\n", "scale": "M", "currency": "USD", "name": "x"})
    assert r.status_code == 400 and "net_income" in r.json()["error"]["message"].lower().replace(" ", "_")
    assert client.get("/api/search", params={"page": 0}).json()["error"]["kind"] == "bad_request"
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setenv("AI_ACCESS_CODE", "letmein")
    wrong = client.post("/api/assistant/ask", json={"symbols": ["AAPL"], "question": "q", "access_code": "nope"})
    assert wrong.status_code == 403 and wrong.json()["error"]["message"] == "Incorrect access code."
    assert alerts == []                                                    # user mistakes never page the owner


# 9. Requested dataset unavailable (explained, not technical) ----------------------------------------
def test_dataset_unavailable(client, alerts, monkeypatch):
    import fip.api
    from conftest import FakeResponse, load_fixture
    real = fip.api.load_financials
    xom = FakeResponse(200, load_fixture("XOM"))
    monkeypatch.setattr(fip.api, "load_financials",
                        lambda cik, **kw: real(cik, fetcher=lambda url, **k: xom, **kw))
    body = visitor_safe(client.get("/api/company/XOM"))
    assert body["error"]["kind"] == "no_annual_data" and body["error"]["retryable"] is False
    assert "No audited annual financial statements" in body["error"]["message"]
    assert visitor_safe(client.get("/api/company/SPY"))["status"] == "not_company"
    assert alerts == []


# 10. Unexpected backend exception ----------------------------------------------------------------------
def test_unexpected_exception(client, alerts, monkeypatch, log_lines):
    import fip.api
    def explode(*a, **k):
        raise KeyError("internal_column_missing")
    monkeypatch.setattr(fip.api, "annual_table", explode)
    r = client.get("/api/company/AAPL")
    body = visitor_safe(r)
    assert r.status_code == 500 and body["error"]["message"] == "Something went wrong. Please try again shortly."
    ref = body["error"]["ref"]
    assert r.headers["X-Request-ID"] == ref
    incident = next(e for e in log_lines if e["event"] == "incident" and e["category"] == "internal")
    assert incident["ref"] == ref and incident["error_type"] == "KeyError" and incident["where"]
    assert len(alerts) == 1 and "CRITICAL" in alerts[0][0] and ref in alerts[0][1]


def test_every_response_has_a_reference(client):
    r = client.get("/api/health")
    assert re.fullmatch(r"FI-[A-Z2-9]{6}", r.headers["X-Request-ID"])


# Alert engine --------------------------------------------------------------------------------------------
def test_alert_threshold_dedup_and_daily_cap(tmp_path):
    from fip.alerts import AlertGate
    now = [1000.0]
    gate = AlertGate(tmp_path / "a.sqlite3", clock=lambda: now[0])
    kw = dict(threshold=3, window_s=600, cooldown_s=3600, daily_max=2)
    assert [gate.decide("sec", **kw)[0] for _ in range(3)] == [False, False, True]   # 3rd occurrence alerts
    assert gate.decide("sec", **kw) == (False, 4, "duplicate within cooldown")
    now[0] += 3601                                    # after the cooldown it must recur past the threshold again
    assert [gate.decide("sec", **kw)[0] for _ in range(3)] == [False, False, True]
    now[0] += 3601
    assert [gate.decide("sec", **kw)[2] for _ in range(3)][-1] == "daily alert cap reached"


def test_alert_email_content_and_secret_scrubbing(monkeypatch):
    from fip.alerts import compose
    from fip.observability import scrub
    subject, body = compose(category="gemini_auth", service="gemini", summary="Gemini rejected the key",
                            ref="FI-TEST22", severity="critical", temporary=False, occurrences=1, window_s=600,
                            detail=scrub(f"key={SECRET} user owner@example.com"))
    assert subject.startswith("[Financial Intelligence V7] CRITICAL")
    for part in ("Financial Intelligence V7", "gemini_auth", "Google Gemini API", "FI-TEST22", "Requires attention",
                 "Time (UTC):"):
        assert part in body
    assert SECRET not in body and "owner@example.com" not in body
    assert scrub({"SMTP_PASSWORD": "p", "authorization": "Bearer x", "ok": "fine"}) == \
        {"SMTP_PASSWORD": "[redacted]", "authorization": "[redacted]", "ok": "fine"}


def test_smtp_delivery_uses_starttls_and_login(monkeypatch):
    import fip.alerts as al
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls["connect"] = (host, port, timeout)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def ehlo(self):
            pass
        def starttls(self, context):
            calls["tls"] = True
        def login(self, user, password):
            calls["login"] = user
        def send_message(self, msg):
            calls["to"], calls["subject"] = msg["To"], msg["Subject"]
    monkeypatch.setattr(al.smtplib, "SMTP", FakeSMTP)
    cfg = {"to": "owner@example.com", "from": "sender@example.com", "smtp_host": "smtp.gmail.com", "smtp_port": 587,
           "smtp_user": "sender@example.com", "smtp_password": "x", "resend_key": "", "enabled": True,
           "cooldown_s": 3600, "daily_max": 20}
    assert al.deliver("subj", "body", cfg) == "smtp"
    assert calls == {"connect": ("smtp.gmail.com", 587, 8), "tls": True, "login": "sender@example.com",
                     "to": "owner@example.com", "subject": "subj"}


def test_alerts_skip_quietly_when_not_configured(monkeypatch):
    import fip.alerts as al
    for k in ("ALERT_EMAIL_TO", "SMTP_HOST", "RESEND_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert al.maybe_alert(category="x", service="backend", summary="s", ref="FI-AAAAAA") == "not configured"


def test_client_error_endpoint_logs_and_alerts_on_repeats(client, alerts):
    for _ in range(3):
        assert client.post("/api/client-error", json={"message": "TypeError: x is undefined", "page": "/compare"}).status_code == 200
    assert len(alerts) == 1 and "frontend" in alerts[0][0]


def test_smtp_falls_back_to_ssl_port_and_strips_app_password_spaces(monkeypatch):
    import smtplib
    import fip.alerts as al
    seen = {}

    class Broken:
        def __init__(self, *a, **k):
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

    class FakeSSL:
        def __init__(self, host, port, timeout, context):
            seen["ssl"] = (host, port)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def login(self, user, password):
            seen["password"] = password
        def send_message(self, msg):
            seen["sent"] = True
    monkeypatch.setattr(al.smtplib, "SMTP", Broken)
    monkeypatch.setattr(al.smtplib, "SMTP_SSL", FakeSSL)
    cfg = {"to": "owner@example.com", "from": "", "smtp_host": "smtp.gmail.com", "smtp_port": 587,
           "smtp_user": "sender@example.com", "smtp_password": "abcd efgh ijkl mnop", "resend_key": "", "enabled": True,
           "cooldown_s": 3600, "daily_max": 20}
    assert al.deliver("subj", "body", cfg) == "smtp"
    assert seen == {"ssl": ("smtp.gmail.com", 465), "password": "abcdefghijklmnop", "sent": True}


def test_delivery_failure_log_is_diagnostic_but_secret_free(monkeypatch, tmp_path, log_lines):
    import smtplib
    import fip.alerts as al
    monkeypatch.setenv("ALERT_EMAIL_TO", "owner@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "supersecretpw")
    monkeypatch.setenv("FIP_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(al, "_GATE", None)

    def boom(*a, **k):
        raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    monkeypatch.setattr(al, "_send_smtp", boom)
    assert al.maybe_alert(category="internal", service="API", summary="x", ref="FI-TEST01", threshold=1,
                          fingerprint="diag-test") == "failed"
    text = json.dumps(log_lines)
    assert "alert_delivery_failed" in text and "SMTPAuthenticationError" in text and "smtp.gmail.com" in text
    assert "supersecretpw" not in text
