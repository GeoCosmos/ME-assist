import pytest

import config
import ratelimit
from llm.base import RateLimited, _retry_after_from, classify_rate_limit


@pytest.fixture(autouse=True)
def clean_pacer():
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_no_wait_when_the_window_is_empty():
    assert ratelimit.wait_needed("gemini", now=1000.0) == 0


def test_wait_kicks_in_before_the_published_ceiling(monkeypatch):
    """We stop one short of the limit rather than discovering it via a 429."""
    monkeypatch.setenv("GEMINI_FREE_RPM", "10")

    for i in range(9):  # limit 10, safety margin 1 -> usable 9
        ratelimit.note_attempt("gemini", now=1000.0 + i)

    assert ratelimit.wait_needed("gemini", now=1010.0) > 0


def test_wait_is_only_as_long_as_the_oldest_slot_needs(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_RPM", "2")
    ratelimit.note_attempt("gemini", now=1000.0)

    # usable = 1, so the window must age out the attempt at t=1000.
    wait = ratelimit.wait_needed("gemini", now=1030.0)
    assert 29 < wait < 32


def test_window_expires(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_RPM", "2")
    ratelimit.note_attempt("gemini", now=1000.0)

    assert ratelimit.wait_needed("gemini", now=1061.0) == 0


def test_groq_gets_its_own_higher_ceiling(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    for i in range(15):
        ratelimit.note_attempt("groq", now=1000.0 + i * 0.1)

    # Groq allows 30/min, so 15 attempts is still fine.
    assert ratelimit.wait_needed("groq", now=1002.0) == 0
    # Gemini would already be blocked at that rate.
    for i in range(15):
        ratelimit.note_attempt("gemini", now=1000.0 + i * 0.1)
    assert ratelimit.wait_needed("gemini", now=1002.0) > 0


def test_paid_providers_are_unpaced_unless_told_otherwise(monkeypatch):
    for i in range(500):
        ratelimit.note_attempt("openai", now=1000.0 + i * 0.01)
    assert ratelimit.wait_needed("openai", now=1005.0) == 0

    monkeypatch.setenv("OPENAI_RPM", "60")
    assert ratelimit.wait_needed("openai", now=1005.0) > 0


def test_observed_429_sets_a_cooldown():
    ratelimit.cooldown("gemini", 30.0, now=1000.0)

    assert ratelimit.wait_needed("gemini", now=1010.0) == pytest.approx(20.0, abs=0.1)
    assert ratelimit.wait_needed("gemini", now=1031.0) == 0


def test_cooldown_takes_the_longer_of_the_two():
    ratelimit.cooldown("gemini", 5.0, now=1000.0)
    ratelimit.cooldown("gemini", 40.0, now=1000.0)

    assert ratelimit.wait_needed("gemini", now=1010.0) > 25


def test_snapshot_reports_position(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_RPM", "10")
    ratelimit.note_attempt("gemini")

    snap = ratelimit.snapshot()
    assert snap["gemini"]["limit_rpm"] == 10
    assert snap["gemini"]["used_in_window"] == 1
    assert snap["openai"]["limit_rpm"] == 0


# --- retry delay parsing -------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"retryDelay": "24s"}', 24.0),
        ("retry-after: 12", 12.0),
        ("Rate limit reached. Please try again in 7.5s", 7.5),
        ("Please retry in 30 seconds", 30.0),
        ("429 Too Many Requests", 8.0),  # default
    ],
)
def test_retry_delay_is_read_from_the_error(text, expected):
    assert _retry_after_from(text) == expected


def test_retry_delay_is_capped():
    assert _retry_after_from("retryDelay: \"9999s\"") == 60.0


def test_groq_style_429_is_retryable_with_its_own_delay():
    exc = Exception(
        "Error code: 429 - rate_limit_exceeded: Rate limit reached for "
        "llama-3.3-70b-versatile. Please try again in 6.2s"
    )
    result = classify_rate_limit(exc, "Groq")
    assert isinstance(result, RateLimited)
    assert result.retry_after == 6.2


# --- tokens per minute ---------------------------------------------------


def test_token_budget_blocks_before_the_request_count_does(monkeypatch):
    """On Groq the token budget, not the request count, is the real ceiling."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GROQ_FREE_TPM", "6000")

    ratelimit.note_tokens("groq", 4000, now=1000.0)

    # One request is nowhere near the 30/min request limit...
    assert ratelimit.wait_needed("groq", now=1001.0) == 0
    # ...but a 3,000-token turn no longer fits the 6,000/min token budget.
    assert ratelimit.wait_needed("groq", now=1001.0, tokens=3000) > 0
    assert ratelimit.wait_needed("groq", now=1001.0, tokens=1500) == 0


def test_a_prompt_bigger_than_the_budget_is_infeasible(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GROQ_FREE_TPM", "6000")

    assert ratelimit.token_wait("groq", 9000) == ratelimit.INFEASIBLE
    assert ratelimit.fits_token_budget("groq", 9000) is False
    assert ratelimit.fits_token_budget("groq", 5000) is True


def test_token_window_ages_out(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GROQ_FREE_TPM", "6000")

    ratelimit.note_tokens("groq", 5000, now=1000.0)
    assert ratelimit.wait_needed("groq", now=1010.0, tokens=3000) > 0
    assert ratelimit.wait_needed("groq", now=1061.0, tokens=3000) == 0


def test_gemini_token_budget_is_roomy(monkeypatch):
    ratelimit.note_tokens("gemini", 50_000, now=1000.0)
    assert ratelimit.wait_needed("gemini", now=1001.0, tokens=10_000) == 0


def test_snapshot_reports_token_position(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    ratelimit.note_tokens("groq", 1234)

    snap = ratelimit.snapshot()
    assert snap["groq"]["tokens_in_window"] == 1234
    assert snap["groq"]["limit_tpm"] == 6000
