"""JSON API used by the React web app (fip/api.py). Offline: bundled listings + bundled financial snapshot."""
import pytest
from fastapi.testclient import TestClient

SECRET = "AIza" + "UnitTestSecretValueThatMustNeverRender01"   # split so the repo secret scanner ignores it


@pytest.fixture()
def client():
    import fip.api
    fip.api._UNIVERSE = None
    fip.api._GUARD = None          # fresh SQLite guard in this test's temporary cache dir
    return TestClient(fip.api.app)


def test_meta_reports_configuration_without_secrets(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["universe"]["total"] > 10_000 and body["gemini_configured"] is True
    assert SECRET not in r.text
    assert r.headers["x-content-type-options"] == "nosniff"


def test_company_payload_has_years_facts_and_insights(client):
    body = client.get("/api/company/AAPL").json()
    assert body["status"] == "ok"
    fin = body["financials"]
    assert fin["currency"] == "USD" and fin["basis"] == "US GAAP" and fin["origin"] == "bundled snapshot"
    last = fin["years"][-1]
    assert last["values"]["revenue"] > 4e11 and 0 < last["ratios"]["net_margin"] < 1
    assert last["facts"]["revenue"]["accession"] and last["filing_index_url"].startswith("https://www.sec.gov/")
    assert fin["insights"] and {"category", "rule", "evidence"} <= set(fin["insights"][0])
    assert body["notices"], "offline fallback must be labelled"
    # restated flag follows the core rule (value really changed), not merely "has an original value"
    flagged = [f for y in fin["years"] for f in y["facts"].values() if f["restated"]]
    assert all(f["original_value"] is not None for f in flagged)


def test_company_states_are_explained_not_fabricated(client):
    assert client.get("/api/company/SPY").json()["status"] == "not_company"
    xom = client.get("/api/company/XOM").json()
    assert xom["status"] == "error" and "financials" not in xom
    missing = client.get("/api/company/ZZZZZZ")
    assert missing.status_code == 404 and missing.json()["status"] == "not_listed"


def test_search_and_symbols(client):
    body = client.get("/api/search", params={"q": "berkshire"}).json()
    assert [r["symbol"] for r in body["rows"]] == ["BRK.A", "BRK.B"]
    paged = client.get("/api/search", params={"page": 2}).json()
    assert paged["page"] == 2 and len(paged["rows"]) == 25
    syms = client.get("/api/symbols", params={"q": "nvid"}).json()["results"]
    assert syms[0]["symbol"] == "NVDA"


def test_compare_uses_listing_names_and_warns_on_currency(client):
    body = client.get("/api/compare", params={"symbols": "AAPL,MSFT,TM,SPY"}).json()
    names = {r["symbol"]: r["company"] for r in body["rows"]}
    assert names["MSFT"] == "Microsoft Corporation"          # not SEC's upper-case entity name
    assert any("different currencies" in w for w in body["warnings"])
    spy = next(c for c in body["companies"] if c["symbol"] == "SPY")
    assert spy["ok"] is False and "not operating companies" in spy["error"]
    assert set(body["series"]) == {"AAPL", "MSFT", "TM"}


def test_csv_exports(client):
    r = client.get("/api/export/company/AAPL.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and "metric_label" in r.text
    assert client.get("/api/export/compare.csv", params={"symbols": "AAPL,MSFT"}).status_code == 200
    assert client.get("/api/export/company/SPY.csv").status_code == 404


def test_upload_valid_and_invalid(client):
    ok = client.post("/api/upload", json={"csv_text": "fiscal_year,revenue,net_income\n2024,100,10\n2025,120,15\n",
                                          "scale": "M", "currency": "USD", "name": "Test Co"})
    assert ok.status_code == 200
    years = ok.json()["years"]
    assert years[-1]["values"]["revenue"] == 120e6 and abs(years[-1]["ratios"]["revenue_growth"] - 0.2) < 1e-9
    bad = client.post("/api/upload", json={"csv_text": "nope\n1\n", "scale": "M", "currency": "USD", "name": "x"})
    assert bad.status_code == 400 and bad.json()["error"]["kind"] == "bad_csv"
    assert client.post("/api/upload", json={"csv_text": "a", "scale": "X", "currency": "USD", "name": "x"}).status_code == 422


def test_assistant_not_configured(client):
    status = client.get("/api/assistant/status").json()
    assert status["configured"] is False and "Performance" in status["presets"]
    r = client.post("/api/assistant/ask", json={"symbols": ["AAPL"], "question": "How did revenue change?"})
    assert r.status_code == 503 and r.json()["error"]["kind"] == "not_configured"


class _GeminiOk:
    status_code = 200
    ok = True

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": "### Key facts\nMOCK-ANSWER [AAPL FY2026 10-K]"}]},
                                "finishReason": "STOP"}]}


def test_assistant_ask_with_mocked_gemini_caches_and_never_leaks_key(client, monkeypatch):
    import fip.gemini
    calls = []
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setattr(fip.gemini.requests, "post", lambda url, **kw: calls.append((url, kw)) or _GeminiOk())
    body = {"symbols": ["AAPL", "SPY"], "question": "How did revenue change?"}
    first = client.post("/api/assistant/ask", json=body)
    assert first.status_code == 200
    data = first.json()
    assert "MOCK-ANSWER" in data["text"] and data["skipped"] == ["SPY"] and data["from_cache"] is False
    assert SECRET not in first.text and SECRET not in calls[0][0] and calls[0][1]["headers"]["x-goog-api-key"] == SECRET
    second = client.post("/api/assistant/ask", json=body)
    assert second.json()["from_cache"] is True and len(calls) == 1


def test_assistant_access_code_and_limits(client, monkeypatch):
    import fip.gemini
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setenv("AI_ACCESS_CODE", "letmein")
    monkeypatch.setenv("AI_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("AI_CLIENT_DAILY_LIMIT", "1")
    monkeypatch.setattr(fip.gemini.requests, "post", lambda url, **kw: _GeminiOk())
    wrong = client.post("/api/assistant/ask", json={"symbols": ["AAPL"], "question": "q1", "access_code": "nope"})
    assert wrong.status_code == 403
    assert client.post("/api/assistant/ask", json={"symbols": ["AAPL"], "question": "q1", "access_code": "letmein"}).status_code == 200
    limited = client.post("/api/assistant/ask", json={"symbols": ["AAPL"], "question": "q2", "access_code": "letmein"})
    assert limited.status_code == 429 and limited.json()["error"]["kind"] == "limit"


def test_visitor_contact_header_is_validated(client, monkeypatch):
    from fip import api
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)

    class Req:
        def __init__(self, value):
            self.headers = {"x-sec-contact": value}
    assert api.contact_email(Req("me@example.com")) == "me@example.com"
    assert api.contact_email(Req("not-an-email")) == ""
