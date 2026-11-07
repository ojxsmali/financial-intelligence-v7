import json

import pytest
import requests

from conftest import FakeResponse, Recorder, load_fixture
from fip.ai_guard import AiGuard, Limits
from fip.gemini import (DEFAULT_CHAIN, FREE_TIER_MODELS, MAX_QUESTION_CHARS, GeminiError, build_fact_pack, generate,
                        resolve_models)
from fip.xbrl import extract_financials

# Built at runtime so the repository secret scanner (test_security.py) does not flag test data.
KEY = "AIza" + "TEST-SECRET-KEY-should-never-leak-123456"
NO_SLEEP = lambda s: None  # noqa: E731


def ok(text="### Key facts\nRevenue rose [AAPL FY2025 10-K]."):
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]})


def err(status, reason=""):
    body = {"error": {"code": status, "status": "X", "details": [{"reason": reason}] if reason else []}}
    return FakeResponse(status, body)


@pytest.fixture(scope="module")
def pack():
    return build_fact_pack([("AAPL", extract_financials(load_fixture("AAPL"))),
                            ("MSFT", extract_financials(load_fixture("MSFT")))])


def test_fact_pack_is_structured_bounded_and_secret_free(pack):
    text = json.dumps(pack)
    assert KEY not in text and "GEMINI" not in text
    aapl = pack["companies"][0]
    assert aapl["amount_unit"] == "USD millions" and len(aapl["annual_periods"]) == 5
    fy25 = next(p for p in aapl["annual_periods"] if p["fiscal_year"] == 2025)
    assert fy25["amounts_in_millions"]["revenue"] == 416161.0
    assert fy25["form"] == "10-K" and fy25["accession"]
    assert "net_margin_pct" in fy25["ratios"]


def test_success_uses_header_not_url_and_system_instruction(pack):
    t = Recorder(ok())
    answer = generate(pack, "Compare margins", KEY, transport=t, sleep=NO_SLEEP)
    assert answer.model == DEFAULT_CHAIN[0]
    call = t.calls[0]
    assert KEY not in call["url"] and call["headers"]["x-goog-api-key"] == KEY
    assert "systemInstruction" in call["json"] and "<<<Compare margins>>>" in call["json"]["contents"][0]["parts"][0]["text"]


def test_503_retries_same_model_then_succeeds(pack):
    t = Recorder(err(503), ok())
    answer = generate(pack, "q", KEY, transport=t, sleep=NO_SLEEP)
    assert answer.model == DEFAULT_CHAIN[0] and len(t.calls) == 2


def test_persistent_503_falls_back_to_next_free_model(pack):
    t = Recorder(err(503), err(503), ok())
    answer = generate(pack, "q", KEY, transport=t, sleep=NO_SLEEP)
    assert answer.model == DEFAULT_CHAIN[1]
    assert all(any(m in c["url"] for m in FREE_TIER_MODELS) for c in t.calls)


def test_quota_429_moves_to_next_free_model_only(pack):
    t = Recorder(err(429), ok())
    assert generate(pack, "q", KEY, transport=t, sleep=NO_SLEEP).model == DEFAULT_CHAIN[1]


def test_quota_exhausted_everywhere_raises_quota_without_paid_fallback(pack):
    t = Recorder(err(429))
    with pytest.raises(GeminiError) as e:
        generate(pack, "q", KEY, transport=t, sleep=NO_SLEEP)
    assert e.value.kind == "quota" and len(t.calls) == len(DEFAULT_CHAIN)
    assert all(any(f"/{m}:" in c["url"] for m in FREE_TIER_MODELS) for c in t.calls)


@pytest.mark.parametrize("response", [err(401), err(403), err(400, "API_KEY_INVALID")])
def test_auth_errors_stop_immediately(pack, response):
    t = Recorder(response)
    with pytest.raises(GeminiError) as e:
        generate(pack, "q", KEY, transport=t, sleep=NO_SLEEP)
    assert e.value.kind == "auth" and len(t.calls) == 1 and KEY not in e.value.user_message


def test_network_error_message_has_no_secret(pack):
    t = Recorder(requests.ConnectionError(f"failed for key {KEY}"))
    with pytest.raises(GeminiError) as e:
        generate(pack, "q", KEY, transport=t, sleep=NO_SLEEP)
    assert e.value.kind == "network" and KEY not in str(e.value)


def test_all_unavailable(pack):
    with pytest.raises(GeminiError) as e:
        generate(pack, "q", KEY, transport=Recorder(err(404)), sleep=NO_SLEEP)
    assert e.value.kind == "unavailable" and KEY not in e.value.user_message


def test_safety_block_and_empty(pack):
    blocked = FakeResponse(200, {"candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]})
    with pytest.raises(GeminiError) as e:
        generate(pack, "q", KEY, transport=Recorder(blocked), sleep=NO_SLEEP)
    assert e.value.kind == "blocked"
    empty = FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": " "}]}, "finishReason": "STOP"}]})
    with pytest.raises(GeminiError) as e:
        generate(pack, "q", KEY, transport=Recorder(empty), sleep=NO_SLEEP)
    assert e.value.kind == "empty"


def test_missing_key_and_bad_questions(pack):
    with pytest.raises(GeminiError) as e:
        generate(pack, "q", "", transport=Recorder(ok()))
    assert e.value.kind == "not_configured"
    for q in ("", "x" * (MAX_QUESTION_CHARS + 1)):
        with pytest.raises(GeminiError):
            generate(pack, q, KEY, transport=Recorder(ok()))


def test_paid_models_rejected_from_configuration():
    models, rejected = resolve_models("gemini-4-argon, gemini-3.1-pro-preview, gemini-2.5-flash-lite")
    assert models == ["gemini-2.5-flash-lite"] and rejected == ["gemini-4-argon", "gemini-3.1-pro-preview"]
    assert resolve_models("gemini-4-argon")[0] == list(DEFAULT_CHAIN)
    assert all("pro" not in m and "argon" not in m for m in FREE_TIER_MODELS)


def test_thought_parts_are_not_shown(pack):
    resp = FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "hidden", "thought": True},
                                                                     {"text": "visible"}]}}]})
    assert generate(pack, "q", KEY, transport=Recorder(resp)).text == "visible"


# ---------------------------------------------------------------- server-side guard
class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


def make_guard(tmp_path, **overrides):
    limits = Limits(**{"enabled": True, "global_per_day": 5, "global_per_minute": 3, "client_per_day": 2,
                       "cooldown_seconds": 10, **overrides})
    clock = Clock()
    return AiGuard(tmp_path / "g.sqlite3", limits, clock), clock


def test_per_client_cooldown_and_daily_cap(tmp_path):
    guard, clock = make_guard(tmp_path)
    a = guard.client_id("1.1.1.1", "s")
    assert guard.reserve(a).allowed
    blocked = guard.reserve(a)
    assert not blocked.allowed and "wait" in blocked.reason
    clock.now += 11
    assert guard.reserve(a).allowed
    clock.now += 11
    assert "used your 2" in guard.reserve(a).reason
    clock.now += 24 * 3600 + 1
    assert guard.reserve(a).allowed                         # rolling window resets


def test_new_session_same_ip_does_not_reset_limits(tmp_path):
    guard, clock = make_guard(tmp_path)
    assert guard.client_id("9.9.9.9", "session-1") == guard.client_id("9.9.9.9", "session-2")


def test_global_minute_and_day_caps(tmp_path):
    guard, clock = make_guard(tmp_path, client_per_day=100, cooldown_seconds=0)
    clients = [guard.client_id(f"10.0.0.{i}", None) for i in range(10)]
    assert all(guard.reserve(c).allowed for c in clients[:3])
    assert "per-minute" in guard.reserve(clients[3]).reason
    clock.now += 61
    assert guard.reserve(clients[3]).allowed and guard.reserve(clients[4]).allowed
    clock.now += 61
    assert "daily AI budget" in guard.reserve(clients[5]).reason


def test_limits_persist_across_guard_instances(tmp_path):
    guard, clock = make_guard(tmp_path)
    c = guard.client_id("2.2.2.2", None)
    guard.reserve(c)
    again = AiGuard(tmp_path / "g.sqlite3", guard.limits, clock)
    assert not again.reserve(c).allowed                     # survives app restarts / new sessions


def test_disabled_switch(tmp_path):
    guard, _ = make_guard(tmp_path, enabled=False)
    assert "disabled" in guard.reserve("x").reason


def test_ip_addresses_are_not_stored(tmp_path):
    guard, _ = make_guard(tmp_path)
    cid = guard.client_id("203.0.113.7", None)
    guard.reserve(cid)
    assert b"203.0.113.7" not in (tmp_path / "g.sqlite3").read_bytes()


def test_answer_cache(tmp_path, pack):
    guard, clock = make_guard(tmp_path)
    key = guard.cache_key(pack, "Compare  Margins", list(DEFAULT_CHAIN))
    assert key == guard.cache_key(pack, "compare margins", list(DEFAULT_CHAIN))
    assert guard.cached_answer(key) is None
    guard.store_answer(key, {"text": "t"})
    assert guard.cached_answer(key) == {"text": "t"}
    clock.now += 2 * 24 * 3600
    assert guard.cached_answer(key) is None


def test_access_code_bruteforce_throttle(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_ACCESS_CODE", "correct-horse")
    guard, _ = make_guard(tmp_path)
    assert guard.access_code_required()
    c = guard.client_id("3.3.3.3", None)
    for _ in range(5):
        assert guard.check_access_code(c, "wrong") == (False, "Incorrect access code.")
    ok, msg = guard.check_access_code(c, "correct-horse")
    assert not ok and "Too many" in msg
    other = guard.client_id("4.4.4.4", None)
    assert guard.check_access_code(other, "correct-horse") == (True, "")
