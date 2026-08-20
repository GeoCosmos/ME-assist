from datetime import timedelta

import config
import usage


def test_cost_of_known_model():
    # 1M in + 1M out on Sonnet 5 at $2 / $10.
    assert usage.cost_of("claude-sonnet-5", 1_000_000, 1_000_000) == 12.0


def test_cost_of_unknown_model_is_not_free():
    assert usage.cost_of("some-new-model", 1_000_000, 0) > 0


def test_record_accumulates_conversation_totals():
    usage.record("openai", "gpt-5", 1000, 500, conversation_id="c1")
    usage.record("openai", "gpt-5", 2000, 500, conversation_id="c1")

    totals = usage.conversation_totals("c1")
    assert totals["turns"] == 2
    assert totals["input_tokens"] == 3000
    assert totals["output_tokens"] == 1000
    assert totals["cost_usd"] > 0


def test_free_requests_are_counted_but_not_billed():
    usage.record("gemini", "gemini-2.5-flash", 5000, 800, "c2", billable=False)

    assert usage.requests_today("gemini") == 1
    assert usage.conversation_totals("c2")["cost_usd"] == 0
    assert usage.spend_today() == 0


def test_free_remaining_counts_down(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_RPD", "3")
    assert usage.free_remaining("gemini") == 3

    usage.record("gemini", "gemini-2.5-flash", 10, 10, billable=False)
    assert usage.free_remaining("gemini") == 2
    assert usage.free_tier_available("gemini") is True


def test_free_tier_unavailable_once_exhausted(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_RPD", "1")
    usage.record("gemini", "gemini-2.5-flash", 10, 10, billable=False)

    assert usage.free_remaining("gemini") == 0
    assert usage.free_tier_available("gemini") is False


def test_paid_providers_have_no_free_tier():
    assert usage.free_remaining("openai") is None
    assert usage.free_tier_available("openai") is False
    assert usage.free_tier_available("anthropic") is False


def test_groq_has_its_own_free_tier():
    assert config.has_free_tier("groq") is True
    assert usage.free_remaining("groq") == config.free_tier_rpd("groq")


def test_billing_flag_removes_free_tier(monkeypatch):
    monkeypatch.setenv("GEMINI_BILLING_ENABLED", "true")
    assert usage.free_tier_available("gemini") is False
    assert usage.free_remaining("gemini") is None


def test_exhaustion_expires_on_its_own():
    past = usage.now_pacific() - timedelta(minutes=1)
    usage.mark_exhausted("gemini", past, "rate_limited")
    assert usage.exhausted_state("gemini") is None


def test_exhaustion_blocks_until_reset():
    future = usage.now_pacific() + timedelta(hours=2)
    usage.mark_exhausted("gemini", future, "free_tier_daily_limit")

    state = usage.exhausted_state("gemini")
    assert state["reason"] == "free_tier_daily_limit"
    assert usage.free_tier_available("gemini") is False


def test_next_reset_is_pacific_midnight():
    reset = usage.next_reset()
    assert (reset.hour, reset.minute) == (0, 0)
    assert reset > usage.now_pacific()


def test_estimate_scales_with_history():
    short = usage.estimate_next_turn("gpt-5", [{"role": "user", "content": "hi"}])
    long = usage.estimate_next_turn(
        "gpt-5", [{"role": "user", "content": "x" * 40000}]
    )
    assert long.input_tokens > short.input_tokens
    assert long.cost_usd > short.cost_usd


# --- daily token budget (the binding limit on a token-metered free tier) ---


def test_tokens_today_sums_input_and_output():
    usage.record("groq", "llama-3.3-70b-versatile", 8000, 400, billable=False)
    usage.record("groq", "llama-3.3-70b-versatile", 3000, 200, billable=False)
    assert usage.tokens_today("groq") == 11600


def test_tokens_remaining_counts_down(monkeypatch):
    monkeypatch.setenv("GROQ_FREE_TPD", "100000")
    assert usage.tokens_remaining("groq") == 100000

    usage.record("groq", "llama-3.3-70b-versatile", 8000, 400, billable=False)
    assert usage.tokens_remaining("groq") == 91600


def test_token_budget_exhaustion_closes_the_free_tier(monkeypatch):
    monkeypatch.setenv("GROQ_FREE_TPD", "10000")
    monkeypatch.setenv("GROQ_FREE_RPD", "1000")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

    usage.record("groq", "llama-3.3-70b-versatile", 9800, 300, billable=False)

    # Plenty of requests left, but the tokens are gone -- and tokens win.
    assert usage.free_remaining("groq") > 900
    assert usage.tokens_remaining("groq") == 0
    assert usage.free_tier_available("groq") is False


def test_no_daily_token_cap_means_unlimited(monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_TPD", "0")
    usage.record("gemini", "gemini-2.5-flash", 500000, 1000, billable=False)
    assert usage.tokens_remaining("gemini") is None
    assert usage.free_tier_available("gemini") is True


def test_free_summary_reports_the_token_budget(monkeypatch):
    monkeypatch.setenv("GROQ_FREE_TPD", "100000")
    usage.record("groq", "llama-3.3-70b-versatile", 8000, 400, billable=False)

    summary = usage.free_summary()["groq"]
    assert summary["tokens_limit"] == 100000
    assert summary["tokens_remaining"] == 91600
    assert summary["tokens_used"] == 8400


def test_token_estimate_errs_high_not_low():
    """Under-estimating lets the daily budget overrun and understates cost."""
    from llm.base import build_full_system_instruction

    # Measured: a 35,480-char prompt really cost ~10,700 tokens (ratio 3.3).
    # The naive chars/4 rule would say 8,870, which is 17% low.
    text = "x" * 35480
    est = usage.estimate_next_turn("gpt-5", [{"role": "user", "content": text}])

    naive = 35480 // 4
    assert est.input_tokens > naive
    assert est.input_tokens >= 10_000
