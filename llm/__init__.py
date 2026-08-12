"""Provider chain with an explicit, non-silent switch to paid providers.

Rules enforced here:

1. Every free provider is tried before any paid one, and a short per-minute
   wait is preferred over spending money. A per-minute ceiling is a 60-second
   problem, not a reason to bill the user.
2. A paid provider is never used without explicit per-conversation approval.
   Instead the stream stops and emits SwitchRequired.
3. Failover only happens before the first token reaches the browser. Once text
   has been emitted, an error stays an error -- half an answer from one model
   silently completed by another is worse than a visible failure.
"""

import time
from collections.abc import Iterator

import config
import ratelimit
import usage as usage_ledger
from llm.anthropic import AnthropicProvider
from llm.base import (
    Event,
    LLMError,
    ProviderSelected,
    QuotaExceeded,
    RateLimited,
    SwitchRequired,
    TextDelta,
    Usage,
    Waiting,
    build_full_system_instruction,
    text_only,
)
from llm.gemini import GeminiProvider
from llm.groq import GroqProvider
from llm.openai import OpenAIProvider

_PROVIDERS = {
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}

MAX_RATE_LIMIT_RETRIES = 1
MAX_WAIT_ROUNDS = 3


def current_model(provider: str | None = None) -> str:
    provider = provider or config.primary_provider()
    if provider not in _PROVIDERS:
        raise LLMError(f"Unknown LLM provider: {provider!r}")
    return config.get_model(provider)


def available_providers() -> list[str]:
    """Chain order, filtered to providers that actually have an API key."""
    return [p for p in config.get_chain() if p in _PROVIDERS and config.is_configured(p)]


def free_provider() -> str | None:
    for provider in available_providers():
        if usage_ledger.free_tier_available(provider):
            return provider
    return None


def free_candidates() -> list[str]:
    """Every configured provider that can answer for free right now."""
    return [p for p in available_providers() if usage_ledger.free_tier_available(p)]


def next_paid_provider(exclude: tuple[str, ...] = ()) -> str | None:
    for provider in available_providers():
        if provider in exclude:
            continue
        if usage_ledger.exhausted_state(provider):
            continue
        # Anything with a live free tier belongs to the free cascade, never the
        # paid gate -- otherwise the user gets asked to approve spending on a
        # provider that would not have charged them.
        if config.has_free_tier(provider):
            continue
        return provider
    return None


def is_free(provider: str) -> bool:
    return usage_ledger.free_tier_available(provider)


def _switch_event(
    from_provider: str | None,
    to_provider: str,
    reason: str,
    history: list[dict],
    conversation_id: str | None,
    domain: str | None = None,
) -> SwitchRequired:
    model = config.get_model(to_provider)
    estimate = usage_ledger.estimate_next_turn(model, history, domain)
    totals = (
        usage_ledger.conversation_totals(conversation_id)
        if conversation_id
        else {"cost_usd": 0.0}
    )
    state = usage_ledger.exhausted_state(from_provider) if from_provider else None
    resets_at = None
    if state:
        resets_at = state["until"].isoformat()
    elif from_provider:
        resets_at = usage_ledger.next_reset().isoformat()

    return SwitchRequired(
        from_provider=from_provider or "",
        to_provider=to_provider,
        to_model=model,
        reason=reason,
        est_input_tokens=estimate.input_tokens,
        est_output_tokens=estimate.output_tokens,
        est_cost_usd=estimate.cost_usd,
        conversation_cost_usd=totals["cost_usd"],
        resets_at=resets_at,
    )


def trim_history(history: list[dict], max_turns: int | None = None) -> list[dict]:
    """Keep only the most recent turns.

    The full history is re-sent every turn, so tokens grow quadratically with
    conversation length. Against a daily token budget that means one long
    thread can consume the entire day's allowance.
    """
    max_turns = config.max_history_turns() if max_turns is None else max_turns
    if max_turns <= 0 or len(history) <= max_turns:
        return history
    trimmed = history[-max_turns:]
    # Never open on an assistant turn -- providers expect a user message first.
    while trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]
    return trimmed or history[-1:]


def _escalation_reason(last_free: str | None) -> tuple[str | None, str]:
    """Why we are asking for money, stated precisely.

    "Your daily free quota is gone" and "the free tier is busy this minute" are
    very different messages, and the user deserves the accurate one.
    """
    for provider in available_providers():
        if not config.has_free_tier(provider):
            continue
        if usage_ledger.tokens_remaining(provider) == 0:
            return provider, "free_tier_daily_token_limit"
        # Either our own counter says the day is spent, or the provider told us
        # so with a per-day 429.
        state = usage_ledger.exhausted_state(provider)
        if usage_ledger.free_remaining(provider) == 0 or (
            state and state["reason"] == "free_tier_daily_limit"
        ):
            return provider, "free_tier_daily_limit"
    if last_free:
        return last_free, "free_tier_rate_limited"
    return None, "no_free_tier_available"


def _run(
    provider: str,
    history: list[dict],
    conversation_id: str | None,
    free: bool,
    domain: str | None = None,
    dropped_turns: int = 0,
) -> Iterator[Event]:
    """Stream one provider, recording usage. Raises before the first token only."""
    model = config.get_model(provider)
    attempts = 0

    while True:
        emitted = False
        try:
            ratelimit.note_attempt(provider)
            stream = _PROVIDERS[provider]().get_response_stream(history, domain)
            for event in stream:
                if isinstance(event, TextDelta):
                    if not emitted:
                        emitted = True
                        yield ProviderSelected(provider, model, free, dropped_turns)
                    yield event
                elif isinstance(event, Usage):
                    # Real token counts beat our estimate for pacing the next turn.
                    ratelimit.note_tokens(
                        provider, event.input_tokens + event.output_tokens
                    )
                    # Record against the provider we selected, not the label the
                    # provider reports, so quota accounting cannot drift.
                    usage_ledger.record(
                        provider=provider,
                        model=event.model or model,
                        input_tokens=event.input_tokens,
                        output_tokens=event.output_tokens,
                        conversation_id=conversation_id,
                        billable=not free,
                    )
                    yield event
            return
        except RateLimited as exc:
            # The provider knows better than our local counter -- feed the
            # observed delay back into the pacer so siblings get tried first.
            ratelimit.cooldown(provider, exc.retry_after)
            if emitted or attempts >= MAX_RATE_LIMIT_RETRIES:
                raise
            attempts += 1
            time.sleep(min(exc.retry_after, 15.0))
        except QuotaExceeded:
            if not emitted:
                usage_ledger.mark_exhausted(
                    provider, usage_ledger.next_reset(), "free_tier_daily_limit"
                )
            raise


def stream_answer(
    history: list[dict],
    conversation_id: str | None = None,
    approved_provider: str | None = None,
    domain: str | None = None,
) -> Iterator[Event]:
    if not history:
        raise LLMError("Cannot get a response for an empty conversation.")

    full_length = len(history)
    history = trim_history(history)
    dropped_turns = full_length - len(history)

    candidates = available_providers()
    if not candidates:
        raise LLMError(
            "No API keys are configured. Open Settings and add a key for at "
            "least one provider."
        )

    tried: list[str] = []
    last_free: str | None = None

    # Estimated size of this turn, used to respect tokens-per-minute budgets.
    # On a small TPM tier this, not the request count, is the real ceiling.
    def _estimate_for(provider: str) -> int:
        est = usage_ledger.estimate_next_turn(
            config.get_model(provider), history, domain
        )
        return est.input_tokens + est.output_tokens

    too_big_for: list[str] = []

    # --- Free cascade ----------------------------------------------------
    # Every free provider is tried, and a short per-minute wait is preferred
    # over escalating to a paid provider. Hitting a 10-per-minute ceiling is
    # not a reason to spend money when the daily free quota is barely touched.
    if approved_provider is None:
        budget = config.max_free_wait_seconds()
        waited = 0.0
        wait_rounds = 0

        while True:
            candidates = []
            for p in free_candidates():
                if p in tried:
                    continue
                # A turn bigger than what is left of the daily token budget
                # cannot be served, and waiting will not help.
                left_today = usage_ledger.tokens_remaining(p)
                if left_today is not None and _estimate_for(p) > left_today:
                    if p not in too_big_for:
                        too_big_for.append(p)
                    continue
                if not ratelimit.fits_token_budget(p, _estimate_for(p)):
                    # No amount of waiting makes this prompt fit; skip it and
                    # report the real problem later.
                    if p not in too_big_for:
                        too_big_for.append(p)
                    continue
                candidates.append(p)
            if not candidates:
                break

            ready = [
                p for p in candidates
                if ratelimit.wait_needed(p, tokens=_estimate_for(p)) <= 0
            ]
            if not ready:
                # Everything free is paced out. Wait for the soonest slot if it
                # lands inside the budget, otherwise fall through to the gate.
                seconds, provider = min(
                    (ratelimit.wait_needed(p, tokens=_estimate_for(p)), p)
                    for p in candidates
                )
                # Bounded on both time and iterations: if a wait somehow does
                # not clear the window, escalate rather than spin.
                if (
                    wait_rounds >= MAX_WAIT_ROUNDS
                    or waited + seconds > budget
                ):
                    last_free = provider
                    break
                wait_rounds += 1
                waited += seconds
                yield Waiting(provider, round(seconds, 1), "per_minute_limit")
                time.sleep(seconds)
                continue

            provider = ready[0]
            tried.append(provider)
            last_free = provider
            emitted = False
            try:
                for event in _run(
                    provider, history, conversation_id, free=True, domain=domain,
                    dropped_turns=dropped_turns,
                ):
                    if isinstance(event, TextDelta):
                        emitted = True
                    yield event
                return
            except (QuotaExceeded, RateLimited):
                # Only move on silently if the user has seen nothing yet. Once
                # text is on screen the failure must surface rather than be
                # papered over by a different model finishing the answer.
                if emitted:
                    raise
                # QuotaExceeded already parked the provider for the day;
                # RateLimited set a short cooldown. Either way, try the next.
                continue

    free_choice = last_free

    # --- Paid path, gated on explicit approval ---------------------------
    paid_choice = next_paid_provider(exclude=tuple(tried))
    if paid_choice is None:
        if too_big_for and not tried:
            names = ", ".join(config.DISPLAY_NAMES.get(p, p) for p in too_big_for)
            hint = (
                " Pick a discipline section in the left panel -- that swaps the "
                "full reference sheet for just that discipline's tables and "
                "roughly halves the prompt."
                if not domain
                else " Start a new conversation to drop the accumulated history."
            )
            raise LLMError(
                f"This request is larger than {names} allows in a single minute "
                f"({_estimate_for(too_big_for[0]):,} tokens estimated)." + hint
            )
        raise LLMError(
            "Every configured provider is rate limited or out of quota. "
            "Free quota resets at "
            f"{usage_ledger.next_reset().strftime('%-I:%M %p %Z on %b %-d')}."
        )

    if approved_provider != paid_choice:
        from_provider, reason = _escalation_reason(free_choice)
        yield _switch_event(
            from_provider=from_provider,
            to_provider=paid_choice,
            reason=reason,
            history=history,
            conversation_id=conversation_id,
            domain=domain,
        )
        return

    yield from _run(
        paid_choice, history, conversation_id, free=False, domain=domain,
        dropped_turns=dropped_turns,
    )


def get_response_stream(history: list[dict]) -> Iterator[str]:
    """Backward-compatible text-only stream (no approval gate, free path only)."""
    return text_only(stream_answer(history))
