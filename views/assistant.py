import json
import logging
from datetime import datetime, timezone

import streamlit as st

from fip import config
from fip.ai_guard import AiGuard
from fip.gemini import (DEFAULT_CHAIN, MAX_COMPANIES, MAX_QUESTION_CHARS, GeminiError, build_fact_pack, generate,
                        resolve_models)
from fip.ui import components as ui
from fip.ui.state import company_bundles, get_universe, option_label

log = logging.getLogger("fip.assistant")

PRESETS = {
    "Performance": "Explain how revenue and profitability changed over the last fiscal years. Which changes are "
                   "largest, and what would need to be checked in the filings to explain them?",
    "Compare": "Compare these companies' revenue growth, operating margin and net margin. Note fiscal-year and "
               "currency differences that limit the comparison.",
    "Operating vs reported": "Compare operating income with reported net income. Where do they diverge, and what "
                             "non-operating items might explain the gap?",
    "Cash quality": "Assess how well net income is backed by operating cash flow and free cash flow.",
}


@st.cache_resource(show_spinner=False)
def _guard() -> AiGuard:
    return AiGuard()


def _client_id(guard: AiGuard) -> str:
    """Per-visitor key. X-Forwarded-For is client-controlled, so it is only honoured when the operator
    confirms a trusted reverse proxy sets it (AI_TRUST_PROXY_HEADERS=true). Global caps apply regardless."""
    try:
        ip = st.context.ip_address
    except Exception:  # not available in every runtime (e.g. AppTest)
        ip = None
    if config.get_bool_setting("AI_TRUST_PROXY_HEADERS", False):
        forwarded = (st.context.headers or {}).get("X-Forwarded-For", "")
        if forwarded:
            ip = forwarded.split(",")[0].strip() or ip
    session = st.session_state.setdefault("_fip_session", datetime.now(timezone.utc).isoformat())
    return guard.client_id(ip, session)


def _apply_preset(name: str) -> None:
    st.session_state["ai_q"] = PRESETS[name]


def main() -> None:
    ui.page_header("AI research assistant", "Gemini explanations grounded in SEC data",
                   "Answers use only the structured figures shown in this app. Facts, calculations and hypotheses are "
                   "kept separate, with fiscal-year citations.")
    guard = _guard()
    configured = config.gemini_configured()
    models, rejected = resolve_models(config.get_setting("GEMINI_MODELS"))
    client = _client_id(guard)
    status = guard.status(client)
    limits = guard.limits

    chips = [ui.chip("Configured" if configured else "Not configured", "ok" if configured else "warn", dot=True),
             ui.chip("Free-tier models only", "info"),
             ui.chip(f"Your remaining questions (24 h): {status.client_remaining}/{limits.client_per_day}"),
             ui.chip(f"Site budget left: {status.global_remaining}/{limits.global_per_day}")]
    if not limits.enabled:
        chips.append(ui.chip("Disabled by owner", "bad"))
    ui.render('<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin:.3rem 0 .8rem">' + "".join(chips) + "</div>")

    if not configured:
        ui.notice("The AI assistant is switched off because no Gemini API key is configured on the server. All "
                  "dashboards, statements and rule-based insights work without it. Site owner: set GEMINI_API_KEY in "
                  "Streamlit secrets or the server environment (see README → Gemini setup). The key is never entered "
                  "or shown in this web page.", "info")
    if rejected:
        st.caption("Ignored non-allowlisted models from GEMINI_MODELS: " + ", ".join(rejected))

    if configured and guard.access_code_required() and not st.session_state.get("ai_unlocked"):
        with st.form("ai_code"):
            st.markdown("**Access code required** — the site owner limits AI usage to invited visitors.")
            code = st.text_input("Access code", type="password", max_chars=128)
            if st.form_submit_button("Unlock"):
                ok, message = guard.check_access_code(client, code)
                if ok:
                    st.session_state["ai_unlocked"] = True
                    st.rerun()
                ui.notice(message, "bad")
        return

    universe = get_universe()
    pool = list(dict.fromkeys([st.session_state["symbol"]] + st.session_state.get("compare", [])))
    default = [st.session_state["symbol"]]
    if "ai_companies" in st.session_state:   # drop selections that left the pool (company/compare list changed)
        st.session_state["ai_companies"] = [s for s in st.session_state["ai_companies"] if s in pool] or default
    chosen = st.multiselect(f"Companies to analyze (max {MAX_COMPANIES})", pool,
                            default=None if "ai_companies" in st.session_state else default,
                            max_selections=MAX_COMPANIES, key="ai_companies",
                            format_func=lambda s: option_label(universe, s),
                            help="Taken from the selected company and your comparison list.")
    st.caption("Presets:")
    cols = st.columns(len(PRESETS))
    for col, name in zip(cols, PRESETS):
        col.button(name, key=f"preset_{name}", on_click=_apply_preset, args=(name,), width="stretch")
    st.session_state.setdefault("ai_q", PRESETS["Performance"])
    question = st.text_area("Research question", key="ai_q", max_chars=MAX_QUESTION_CHARS, height=110)

    can_ask = configured and limits.enabled and bool(chosen) and bool(question.strip())
    ask = st.button("Generate analysis", type="primary", disabled=not can_ask, key="ai_go")

    if ask:
        with st.spinner("Loading SEC data…"):
            bundles = company_bundles(chosen)
        items = [(b.symbol, b.result.financials) for b in bundles if b.has_financials]
        skipped = [b.symbol for b in bundles if not b.has_financials]
        if skipped:
            ui.notice("Skipped (no annual SEC financial data): " + ", ".join(skipped))
        if not items:
            ui.notice("None of the selected companies has annual SEC financial statements to analyze.", "bad")
        else:
            fact_pack = build_fact_pack(items)
            key = guard.cache_key(fact_pack, question, models)
            cached = guard.cached_answer(key)
            if cached:
                st.session_state["ai_answer"] = {**cached, "from_cache": True}
            else:
                decision = guard.reserve(client)
                if not decision.allowed:
                    ui.notice(decision.reason, "bad")
                else:
                    try:
                        with st.spinner("Asking Gemini (free tier)…"):
                            answer = generate(fact_pack, question, config.gemini_api_key(), models=models)
                        payload = {"text": answer.text, "model": answer.model, "symbols": [s for s, _ in items],
                                   "question": question, "fact_pack": fact_pack,
                                   "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
                        guard.store_answer(key, payload)
                        st.session_state["ai_answer"] = {**payload, "from_cache": False}
                    except GeminiError as exc:
                        log.warning("Gemini request failed: kind=%s", exc.kind)  # no key, no payload
                        ui.notice(exc.user_message, "bad")

    answer = st.session_state.get("ai_answer")
    if answer:
        with st.container(border=True):
            meta = [ui.chip(answer["model"], "info"), ui.chip(answer["at"]),
                    ui.chip(", ".join(answer["symbols"]), "sym")]
            if answer.get("from_cache"):
                meta.append(ui.chip("Cached answer · no quota used", "ok"))
            ui.render('<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.5rem">' + "".join(meta)
                      + "</div>")
            st.markdown(answer["text"])
            st.caption("AI-generated text can contain mistakes. Every figure should be checked against the cited "
                       "filing (Sources & Methodology). Not investment advice.")
        with st.expander("Exactly what was sent to Gemini (fact pack)"):
            st.caption("Structured SEC figures in millions of the reporting currency, plus your question. No API key, "
                       "personal data or browsing history is sent.")
            st.code(json.dumps(answer["fact_pack"], indent=1)[:20000], language="json")

    with st.expander("How the assistant is protected"):
        st.markdown(
            f"""
- The Gemini key lives only in server-side configuration (`GEMINI_API_KEY`); this page never receives it.
- Models are restricted to Google's **free-tier** allowlist (`{', '.join(DEFAULT_CHAIN)}` by default). There is no
  paid fallback; quota errors simply pause the assistant.
- Server-side limits (shared by all visitors): {limits.client_per_day} questions per visitor per 24 h,
  {limits.global_per_day} per site per 24 h, {limits.global_per_minute} per minute, {limits.cooldown_seconds} s cooldown.
- Identical questions about identical data are answered from a 24 h cache without using quota.
- Questions are limited to {MAX_QUESTION_CHARS} characters and {MAX_COMPANIES} companies; the model is instructed to
  treat them as data, not instructions.
"""
        )


main()
