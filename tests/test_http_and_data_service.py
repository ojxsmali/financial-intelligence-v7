import json

import pytest
import requests

from conftest import FakeResponse, Recorder, load_fixture
from fip import data_service
from fip.http_client import (AccessDeniedError, ConfigurationError, NotFoundError, RateLimitedError,
                             UpstreamUnavailableError, fetch, sec_user_agent)

EMAIL = "tester@example.com"
NO_SLEEP = lambda s: None  # noqa: E731


def test_user_agent_requires_contact():
    with pytest.raises(ConfigurationError):
        sec_user_agent("")
    assert EMAIL in sec_user_agent(EMAIL)


def test_success_sends_identifying_headers_and_timeout():
    t = Recorder(FakeResponse(200, {"ok": 1}))
    result = fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL, transport=t, sleep=NO_SLEEP)
    assert result.status == 200
    call = t.calls[0]
    assert EMAIL in call["headers"]["User-Agent"] and "gzip" in call["headers"]["Accept-Encoding"]
    assert call["timeout"]


def test_429_retries_with_retry_after_then_succeeds():
    sleeps = []
    t = Recorder(FakeResponse(429, headers={"Retry-After": "2"}), FakeResponse(200, {"ok": 1}))
    fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL, transport=t, sleep=sleeps.append)
    assert sleeps == [2.0] and len(t.calls) == 2


@pytest.mark.parametrize("status", [500, 502, 503])
def test_server_errors_exhaust_retries(status):
    t = Recorder(FakeResponse(status))
    with pytest.raises(UpstreamUnavailableError) as err:
        fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL, transport=t, sleep=NO_SLEEP)
    assert len(t.calls) == 4 and str(status) in err.value.user_message


def test_persistent_429_raises_rate_limited():
    t = Recorder(FakeResponse(429))
    with pytest.raises(RateLimitedError):
        fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL, transport=t, sleep=NO_SLEEP)


def test_403_and_404_do_not_retry():
    t = Recorder(FakeResponse(403))
    with pytest.raises(AccessDeniedError):
        fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL, transport=t, sleep=NO_SLEEP)
    assert len(t.calls) == 1
    t = Recorder(FakeResponse(404))
    with pytest.raises(NotFoundError):
        fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL, transport=t, sleep=NO_SLEEP)
    assert len(t.calls) == 1


def test_connection_errors_retry_then_fail_cleanly():
    t = Recorder(requests.ConnectionError("boom"))
    with pytest.raises(UpstreamUnavailableError) as err:
        fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL, transport=t, sleep=NO_SLEEP)
    assert len(t.calls) == 4 and "boom" not in err.value.user_message


def test_offline_mode_blocks_network():
    with pytest.raises(UpstreamUnavailableError):
        fetch("https://data.sec.gov/x", sec=True, contact_email=EMAIL)


# ---------------------------------------------------------------- data service fallbacks
class FakeResult:
    def __init__(self, payload):
        self.content = json.dumps(payload).encode()


def live(payload):
    return lambda url, **kw: FakeResult(payload)


def failing(exc):
    def _f(url, **kw):
        raise exc
    return _f


def test_live_then_disk_cache():
    first = data_service.load_financials(320193, fetcher=live(load_fixture("AAPL")), contact_email=EMAIL)
    assert first.ok and first.origin == "live"
    second = data_service.load_financials(320193, fetcher=failing(AssertionError("must not fetch")))
    assert second.ok and second.origin == "disk cache"
    assert second.financials.latest.value("revenue") == first.financials.latest.value("revenue")


def test_stale_cache_used_with_visible_notice_when_sec_fails():
    data_service.load_financials(320193, fetcher=live(load_fixture("AAPL")), contact_email=EMAIL)
    result = data_service.load_financials(320193, force_refresh=True,
                                          fetcher=failing(UpstreamUnavailableError("SEC is down (HTTP 503).")))
    assert result.ok and result.origin == "disk cache (stale)"
    assert result.notices and "503" in result.notices[0]


def test_bundled_snapshot_fallback(monkeypatch, tmp_path):
    from fip.xbrl import extract_financials
    snap_dir = tmp_path / "snap"
    monkeypatch.setattr(data_service, "SNAPSHOT_DIR", snap_dir)
    fin = extract_financials(load_fixture("MSFT"))
    snap_dir.mkdir()
    (snap_dir / f"CIK{fin.cik:010d}.json").write_text(json.dumps(fin.to_dict()))
    result = data_service.load_financials(fin.cik, fetcher=failing(AccessDeniedError("SEC refused (HTTP 403).")))
    assert result.ok and result.origin == "bundled snapshot"
    assert "403" in result.notices[0] and "snapshot" in result.notices[0]


def test_no_data_anywhere_is_an_error_not_a_substitution():
    result = data_service.load_financials(123, fetcher=failing(UpstreamUnavailableError("down")))
    assert not result.ok and result.error_kind == "upstream" and result.financials is None


def test_404_explained():
    result = data_service.load_financials(123, fetcher=failing(NotFoundError("404")))
    assert not result.ok and result.error_kind == "not_found"


def test_no_annual_data_is_cached_and_explained():
    result = data_service.load_financials(2115436, fetcher=live(load_fixture("XOM")))
    assert not result.ok and result.error_kind == "no_annual_data"
    again = data_service.load_financials(2115436, fetcher=failing(AssertionError("must not fetch")))
    assert again.error_kind == "no_annual_data"


def test_missing_contact_email_reports_config_error():
    result = data_service.load_financials(123, fetcher=failing(ConfigurationError("need email")))
    assert not result.ok and result.error_kind == "config"


def test_missing_contact_email_still_serves_labelled_snapshot():
    result = data_service.load_financials(320193, fetcher=failing(ConfigurationError("need email")))
    assert result.ok and result.origin == "bundled snapshot" and result.notices
