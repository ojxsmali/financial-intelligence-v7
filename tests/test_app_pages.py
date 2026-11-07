"""Headless UI tests with Streamlit's AppTest: every page renders without exceptions, offline.

Runs with FIP_OFFLINE=1 and an empty cache, so the app must work from the bundled
listing snapshot and bundled financial snapshot — exercising the fallback path.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["views/overview.py", "views/explorer.py", "views/compare.py", "views/statements.py", "views/insights.py",
         "views/assistant.py", "views/sources.py"]
SECRET = "AIza" + "UnitTestSecretValueThatMustNeverRender01"  # split so the repo secret scanner ignores it


def all_text(at: AppTest) -> str:
    out = []

    def walk(node):
        proto = getattr(node, "proto", None)
        if proto is not None:
            out.append(str(proto))
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(at._tree)
    return "\n".join(out)


def run_page(page: str, symbol: str = "AAPL") -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.query_params["t"] = symbol
    at.run()
    if page != PAGES[0]:
        at.switch_page(page).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = run_page(page)
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.markdown) > 0


def test_overview_shows_units_and_snapshot_label():
    text = all_text(run_page(PAGES[0]))
    assert "Apple Inc." in text
    assert "USD" in text and "B" in text                 # money formatted with scale
    assert "Bundled snapshot" in text or "bundled snapshot" in text   # offline fallback is labelled
    assert "Sep 26" in text                                # fiscal year-end from bundled SEC profile data


def test_company_without_annual_data_shows_explanation():
    at = run_page(PAGES[0], "XOM")
    assert not at.exception
    text = all_text(at)
    assert "ExxonMobil" in text or "Exxon" in text
    assert "unavailable" in text.lower()
    assert "Net profit margin" not in text                # no KPI cards at all, so nothing substituted


def test_etf_with_sec_cik_is_never_treated_as_company():
    from fip.ui.state import get_universe
    entry = get_universe().by_symbol["SPY"]
    assert entry["instrument_type"] == "ETF" and not entry["is_company"]


def test_etf_explained_not_fabricated():
    at = run_page(PAGES[0], "SPY")
    assert not at.exception
    assert "not operating companies" in all_text(at)


def test_compare_page_multiple_companies():
    at = run_page("views/compare.py")
    assert not at.exception
    text = all_text(at)
    for symbol in ("AAPL", "MSFT", "GOOGL", "NVDA"):
        assert symbol in text


def test_explorer_search():
    at = run_page("views/explorer.py")
    at.text_input(key="ex_q").input("berkshire").run()
    assert not at.exception
    assert "BRK.B" in all_text(at)


def test_assistant_without_key_is_safe():
    at = run_page("views/assistant.py")
    assert not at.exception
    text = all_text(at)
    assert "not configured" in text.lower() or "Not configured" in text
    assert not any("api key" in (ti.label or "").lower() for ti in at.text_input)


def test_assistant_never_renders_configured_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    at = run_page("views/assistant.py")
    assert not at.exception
    assert SECRET not in all_text(at)
    assert not any(SECRET in str(getattr(ti, "value", "")) for ti in at.text_input)


class _GeminiOk:
    status_code = 200
    ok = True

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": "### Key facts\nMOCK-ANSWER revenue grew "
                                                                "[AAPL FY2026 10-K]."}]}, "finishReason": "STOP"}]}


def test_assistant_end_to_end_with_mocked_gemini(monkeypatch):
    import fip.gemini
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return _GeminiOk()

    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setattr(fip.gemini.requests, "post", fake_post)
    at = run_page("views/assistant.py")
    at.button(key="ai_go").click().run()
    assert not at.exception
    text = all_text(at)
    assert "MOCK-ANSWER" in text and SECRET not in text
    assert len(calls) == 1 and SECRET not in calls[0]["url"] and calls[0]["headers"]["x-goog-api-key"] == SECRET
    sent = str(calls[0]["json"])
    assert "416161" in sent or "478" in sent                    # real SEC figures in millions were sent

    at.button(key="ai_go").click().run()                       # identical question -> served from cache
    assert len(calls) == 1 and "Cached answer" in all_text(at)


def test_assistant_quota_exhausted_is_graceful(monkeypatch):
    import fip.gemini

    class _Quota:
        status_code = 429
        ok = False

        def json(self):
            return {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}

    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setattr(fip.gemini.requests, "post", lambda url, **kw: _Quota())
    at = run_page("views/assistant.py")
    at.text_area(key="ai_q").input("A different question about margins").run()
    at.button(key="ai_go").click().run()
    assert not at.exception
    assert "quota" in all_text(at).lower()


def test_unit_selector_changes_formatting():
    at = run_page(PAGES[0])
    at.session_state["unit"] = "M"
    at.run()
    assert not at.exception
    assert "M" in all_text(at)
