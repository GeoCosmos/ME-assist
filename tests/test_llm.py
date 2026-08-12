import pytest

import llm
import usage
from llm import stream_answer
from llm.base import (
    LLMError,
    ProviderSelected,
    QuotaExceeded,
    RateLimited,
    SwitchRequired,
    TextDelta,
    Usage,
    build_full_system_instruction,
    classify_rate_limit,
)


def fake_provider(text="answer", tokens=(100, 50), error=None):
    class Fake:
        def get_response_stream(self, history, domain=None):
            if error is not None:
                raise error
            yield TextDelta(text)
            yield Usage("x", "x", *tokens)

    return Fake


def install(monkeypatch, provider, cls):
    monkeypatch.setitem(llm._PROVIDERS, provider, cls)


def texts(events):
    return "".join(e.text for e in events if isinstance(e, TextDelta))


# --- basics --------------------------------------------------------------


def test_build_full_system_instruction_includes_persona_and_reference_data():
    instruction = build_full_system_instruction()
    assert "mechanical engineering assistant" in instruction.lower()
    assert "6061-T6" in instruction


def test_empty_history_raises():
    with pytest.raises(LLMError):
        list(stream_answer([]))


def test_no_configured_provider_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="No API keys"):
        list(stream_answer([{"role": "user", "content": "hi"}]))


def test_all_four_providers_are_registered():
    assert set(llm._PROVIDERS) == {"gemini", "groq", "anthropic", "openai"}


# --- free path -----------------------------------------------------------


def test_free_provider_answers_without_asking(monkeypatch):
    install(monkeypatch, "gemini", fake_provider("free answer"))

    events = list(stream_answer([{"role": "user", "content": "hi"}], "c1"))

    assert texts(events) == "free answer"
    assert not any(isinstance(e, SwitchRequired) for e in events)
    selected = [e for e in events if isinstance(e, ProviderSelected)]
    assert selected[0].provider == "gemini"
    assert selected[0].free is True
    # Free turns are logged for quota counting but cost nothing.
    assert usage.requests_today("gemini") == 1
    assert usage.conversation_totals("c1")["cost_usd"] == 0


def test_groq_is_used_as_a_second_free_tier(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")
    install(monkeypatch, "groq", fake_provider("groq answer"))

    events = list(stream_answer([{"role": "user", "content": "hi"}], "c1"))

    assert texts(events) == "groq answer"
    assert not any(isinstance(e, SwitchRequired) for e in events)


# --- the approval gate ---------------------------------------------------


def test_paid_provider_is_never_used_without_approval(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")

    called = []

    class Spy:
        def get_response_stream(self, history, domain=None):
            called.append(True)
            yield TextDelta("should not happen")

    install(monkeypatch, "openai", Spy)

    events = list(stream_answer([{"role": "user", "content": "hi"}], "c1"))

    assert called == []  # the paid provider was never contacted
    switches = [e for e in events if isinstance(e, SwitchRequired)]
    assert len(switches) == 1
    assert switches[0].to_provider == "openai"
    assert switches[0].est_cost_usd > 0
    assert texts(events) == ""


def test_approved_paid_provider_runs_and_is_billed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")
    install(monkeypatch, "openai", fake_provider("paid answer", (1000, 500)))

    events = list(
        stream_answer([{"role": "user", "content": "hi"}], "c1", approved_provider="openai")
    )

    assert texts(events) == "paid answer"
    selected = [e for e in events if isinstance(e, ProviderSelected)]
    assert selected[0].free is False
    assert usage.conversation_totals("c1")["cost_usd"] > 0


def test_approval_for_one_provider_does_not_authorise_another(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("LLM_CHAIN", "gemini,openai,anthropic")
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")

    events = list(
        stream_answer(
            [{"role": "user", "content": "hi"}], "c1", approved_provider="anthropic"
        )
    )

    switches = [e for e in events if isinstance(e, SwitchRequired)]
    assert len(switches) == 1
    assert switches[0].to_provider == "openai"


def test_quota_exhaustion_mid_request_triggers_the_gate(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    install(
        monkeypatch,
        "gemini",
        fake_provider(error=QuotaExceeded("out of free quota")),
    )

    events = list(stream_answer([{"role": "user", "content": "hi"}], "c1"))

    switches = [e for e in events if isinstance(e, SwitchRequired)]
    assert len(switches) == 1
    assert switches[0].from_provider == "gemini"
    assert switches[0].reason == "free_tier_daily_limit"
    # Gemini is now parked until the quota resets.
    assert usage.exhausted_state("gemini") is not None


def test_switch_event_reports_spend_so_far(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")
    usage.record("openai", "gpt-5", 100_000, 10_000, conversation_id="c1")

    events = list(stream_answer([{"role": "user", "content": "hi"}], "c1"))
    switch = next(e for e in events if isinstance(e, SwitchRequired))

    assert switch.conversation_cost_usd > 0


def test_no_provider_left_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")

    with pytest.raises(LLMError, match="rate limited or out of quota"):
        list(stream_answer([{"role": "user", "content": "hi"}], "c1"))


# --- mid-stream behaviour ------------------------------------------------


def test_failure_after_first_token_does_not_fail_over(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class HalfWay:
        def get_response_stream(self, history, domain=None):
            yield TextDelta("half an ")
            raise QuotaExceeded("died mid-answer")

    openai_called = []

    class Spy:
        def get_response_stream(self, history, domain=None):
            openai_called.append(True)
            yield TextDelta("rest of it")

    install(monkeypatch, "gemini", HalfWay)
    install(monkeypatch, "openai", Spy)

    with pytest.raises(QuotaExceeded):
        list(stream_answer([{"role": "user", "content": "hi"}], "c1"))

    # Critically: no silent stitching of two models into one answer.
    assert openai_called == []


def test_rate_limit_retries_once_then_gives_up(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    attempts = []

    class Flaky:
        def get_response_stream(self, history, domain=None):
            attempts.append(True)
            raise RateLimited("slow down", retry_after=0.01)
            yield  # pragma: no cover

    install(monkeypatch, "gemini", Flaky)
    monkeypatch.setenv("GEMINI_FREE_RPD", "100")

    # Gemini is the only key configured, so once it is rate limited there is
    # nowhere to go and the user gets a visible error rather than silence.
    with pytest.raises(LLMError):
        list(stream_answer([{"role": "user", "content": "hi"}], "c1"))

    assert len(attempts) == 2  # initial try + one retry


def test_exhausted_free_provider_is_not_offered_as_a_paid_option(monkeypatch):
    """Without billing enabled, a spent free tier is unusable, not billable."""
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")

    with pytest.raises(LLMError, match="rate limited or out of quota"):
        list(stream_answer([{"role": "user", "content": "hi"}], "c1"))


# --- 429 classification --------------------------------------------------


def test_daily_quota_429_is_classified_as_exhausted():
    exc = Exception("429 RESOURCE_EXHAUSTED quota_metric generate_requests_per_day")
    assert isinstance(classify_rate_limit(exc, "Gemini"), QuotaExceeded)


def test_per_minute_429_is_classified_as_retryable():
    exc = Exception("429 RESOURCE_EXHAUSTED GenerateRequestsPerMinute retry in 12s")
    result = classify_rate_limit(exc, "Gemini")
    assert isinstance(result, RateLimited)
    assert result.retry_after == 12.0


def test_ambiguous_429_defaults_to_retryable_not_a_day_long_ban():
    result = classify_rate_limit(Exception("429 Too Many Requests"), "Groq")
    assert isinstance(result, RateLimited)
    assert not isinstance(result, QuotaExceeded)


def test_non_429_stays_a_plain_error():
    result = classify_rate_limit(Exception("connection reset"), "OpenAI")
    assert isinstance(result, LLMError)
    assert not isinstance(result, (RateLimited, QuotaExceeded))


# --- history trimming ----------------------------------------------------


def test_history_is_trimmed_to_the_configured_window(monkeypatch):
    """Re-sending an unbounded history burns a daily token budget fast."""
    monkeypatch.setenv("MAX_HISTORY_TURNS", "4")
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"q{i}"})
        history.append({"role": "model", "content": f"a{i}"})

    trimmed = llm.trim_history(history)

    assert len(trimmed) == 4
    assert trimmed[-1]["content"] == "a9"
    assert trimmed[0]["role"] == "user"


def test_trimming_never_starts_on_an_assistant_turn(monkeypatch):
    monkeypatch.setenv("MAX_HISTORY_TURNS", "3")
    history = [
        {"role": "user", "content": "q1"},
        {"role": "model", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "model", "content": "a2"},
    ]
    trimmed = llm.trim_history(history)
    assert trimmed[0]["role"] == "user"


def test_short_history_is_untouched(monkeypatch):
    monkeypatch.setenv("MAX_HISTORY_TURNS", "10")
    history = [{"role": "user", "content": "only one"}]
    assert llm.trim_history(history) == history


def test_trimming_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MAX_HISTORY_TURNS", "0")
    history = [{"role": "user", "content": f"q{i}"} for i in range(40)]
    assert llm.trim_history(history) == history


def test_daily_token_exhaustion_reaches_the_gate_with_its_own_reason(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("LLM_CHAIN", "groq,openai")
    monkeypatch.setenv("GROQ_FREE_TPD", "5000")
    usage.record("groq", "llama-3.3-70b-versatile", 5000, 100, billable=False)

    events = list(stream_answer([{"role": "user", "content": "hi"}], "c1"))
    switches = [e for e in events if isinstance(e, SwitchRequired)]

    assert len(switches) == 1
    assert switches[0].reason == "free_tier_daily_token_limit"


def test_dropped_turns_are_reported_not_hidden(monkeypatch):
    """Silently forgetting the start of a thread produces confident wrong answers."""
    monkeypatch.setenv("MAX_HISTORY_TURNS", "4")
    install(monkeypatch, "gemini", fake_provider("answer"))

    history = []
    for i in range(6):
        history.append({"role": "user", "content": f"q{i}"})
        history.append({"role": "model", "content": f"a{i}"})

    events = list(stream_answer(history, "c1"))
    selected = [e for e in events if isinstance(e, ProviderSelected)][0]

    assert selected.dropped_turns == 8


def test_nothing_dropped_reports_zero(monkeypatch):
    monkeypatch.setenv("MAX_HISTORY_TURNS", "20")
    install(monkeypatch, "gemini", fake_provider("answer"))

    events = list(stream_answer([{"role": "user", "content": "hi"}], "c1"))
    selected = [e for e in events if isinstance(e, ProviderSelected)][0]

    assert selected.dropped_turns == 0
