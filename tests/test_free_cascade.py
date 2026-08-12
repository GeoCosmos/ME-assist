"""The per-minute trap: a 60-second limit must never become a bill."""

import pytest

import llm
import ratelimit
import usage
from llm import stream_answer
from llm.base import (
    LLMError,
    ProviderSelected,
    RateLimited,
    SwitchRequired,
    TextDelta,
    Usage,
    Waiting,
)


@pytest.fixture(autouse=True)
def clean_pacer():
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture(autouse=True)
def no_real_sleeping(monkeypatch):
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    return slept


def provider_yielding(text, tokens=(100, 50)):
    class P:
        def get_response_stream(self, history, domain=None):
            yield TextDelta(text)
            yield Usage("x", "x", *tokens)

    return P


def provider_raising(error):
    class P:
        def get_response_stream(self, history, domain=None):
            raise error
            yield  # pragma: no cover

    return P


def install(monkeypatch, name, cls):
    monkeypatch.setitem(llm._PROVIDERS, name, cls)


def texts(events):
    return "".join(e.text for e in events if isinstance(e, TextDelta))


def ask(**kwargs):
    return list(stream_answer([{"role": "user", "content": "hi"}], "c1", **kwargs))


def test_minute_limit_on_one_free_tier_falls_to_the_other(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini,groq,openai,anthropic")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    install(monkeypatch, "gemini", provider_raising(RateLimited("slow down", 20.0)))
    install(monkeypatch, "groq", provider_yielding("groq answer"))

    events = ask()

    assert texts(events) == "groq answer"
    # Crucially: no money prompt for a per-minute blip.
    assert not any(isinstance(e, SwitchRequired) for e in events)


def test_pacing_skips_a_provider_before_it_429s(monkeypatch):
    """Gemini is already at its ceiling, so it is not even contacted."""
    monkeypatch.setenv("LLM_CHAIN", "gemini,groq,openai,anthropic")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GEMINI_FREE_RPM", "2")

    gemini_called = []

    class Gemini:
        def get_response_stream(self, history, domain=None):
            gemini_called.append(True)
            yield TextDelta("should not happen")

    install(monkeypatch, "gemini", Gemini)
    install(monkeypatch, "groq", provider_yielding("groq answer"))

    ratelimit.note_attempt("gemini")  # usable = 1, so gemini is now paced out

    events = ask()

    assert gemini_called == []
    assert texts(events) == "groq answer"


def test_short_wait_is_preferred_over_paying(monkeypatch):
    """Only free provider is minute-limited: wait it out, do not ask for money."""
    import time as real_time

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPM", "2")
    monkeypatch.setenv("MAX_FREE_WAIT_SECONDS", "60")
    install(monkeypatch, "gemini", provider_yielding("free answer"))

    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)
        ratelimit.reset()  # the window has aged out while we waited

    monkeypatch.setattr(llm.time, "sleep", fake_sleep)
    ratelimit.note_attempt("gemini", now=real_time.time() - 45)

    events = ask()

    waits = [e for e in events if isinstance(e, Waiting)]
    assert len(waits) == 1
    assert waits[0].reason == "per_minute_limit"
    assert 10 < slept[0] < 20  # waited roughly the remaining window, not a flat guess
    assert texts(events) == "free answer"
    assert not any(isinstance(e, SwitchRequired) for e in events)


def test_a_wait_that_never_clears_escalates_instead_of_spinning(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPM", "2")
    monkeypatch.setenv("MAX_FREE_WAIT_SECONDS", "600")
    install(monkeypatch, "gemini", provider_yielding("free answer"))

    # Sleep that does not advance the window at all.
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    ratelimit.note_attempt("gemini")

    events = ask()

    assert len([e for e in events if isinstance(e, Waiting)]) <= llm.MAX_WAIT_ROUNDS
    assert any(isinstance(e, SwitchRequired) for e in events)


def test_long_wait_escalates_to_the_gate(monkeypatch):
    """If free capacity is minutes away, ask rather than hang."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_FREE_WAIT_SECONDS", "5")
    install(monkeypatch, "gemini", provider_yielding("free answer"))

    ratelimit.cooldown("gemini", 300.0)

    events = ask()

    switches = [e for e in events if isinstance(e, SwitchRequired)]
    assert len(switches) == 1
    assert switches[0].to_provider == "openai"


def test_a_free_provider_is_never_offered_as_a_paid_switch(monkeypatch):
    """Groq is free -- approving a paid switch to it would be nonsense."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("MAX_FREE_WAIT_SECONDS", "0")
    ratelimit.cooldown("gemini", 300.0)
    ratelimit.cooldown("groq", 300.0)

    with pytest.raises(LLMError, match="rate limited or out of quota"):
        ask()


def test_all_free_tiers_are_tried_before_the_gate(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini,groq,openai,anthropic")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_FREE_WAIT_SECONDS", "0")
    install(monkeypatch, "gemini", provider_raising(RateLimited("busy", 300.0)))
    install(monkeypatch, "groq", provider_raising(RateLimited("busy", 300.0)))

    events = ask()

    switches = [e for e in events if isinstance(e, SwitchRequired)]
    assert len(switches) == 1
    assert switches[0].to_provider == "openai"
    assert switches[0].from_provider == "groq"  # the last free one tried


def test_a_429_feeds_back_into_the_pacer(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini,groq,openai,anthropic")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    install(monkeypatch, "gemini", provider_raising(RateLimited("slow down", 30.0)))
    install(monkeypatch, "groq", provider_yielding("groq answer"))

    ask()

    # Gemini is parked for the delay it asked for, so the next question goes
    # straight to Groq instead of burning another round trip.
    assert ratelimit.wait_needed("gemini") > 25


def test_daily_exhaustion_still_reaches_the_gate(monkeypatch):
    """A per-day limit is a real reason to ask -- unlike a per-minute one."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")

    events = ask()

    switches = [e for e in events if isinstance(e, SwitchRequired)]
    assert len(switches) == 1
    assert switches[0].reason == "free_tier_daily_limit"


def test_successful_free_turn_is_paced(monkeypatch):
    install(monkeypatch, "gemini", provider_yielding("answer"))

    ask()

    assert ratelimit.snapshot()["gemini"]["used_in_window"] == 1


def test_mid_stream_rate_limit_still_does_not_fail_over(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini,groq,openai,anthropic")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

    class HalfWay:
        def get_response_stream(self, history, domain=None):
            yield TextDelta("half an ")
            raise RateLimited("died mid-answer", 5.0)

    groq_called = []

    class Groq:
        def get_response_stream(self, history, domain=None):
            groq_called.append(True)
            yield TextDelta("rest")

    install(monkeypatch, "gemini", HalfWay)
    install(monkeypatch, "groq", Groq)

    with pytest.raises(RateLimited):
        ask()

    assert groq_called == []
