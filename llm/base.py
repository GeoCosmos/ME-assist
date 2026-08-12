import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

import domains
import reference_data
from system_prompt import SYSTEM_PROMPT


class LLMError(Exception):
    """Raised when an LLM provider call fails or the request is invalid."""


class RateLimited(LLMError):
    """Short-term rate limit (requests per minute). Retryable on the same provider."""

    def __init__(self, message: str, retry_after: float = 10.0):
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExceeded(LLMError):
    """Daily free-tier quota is gone. Not retryable until the quota resets."""


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Usage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ProviderSelected:
    """Emitted before the first token so the UI always names who is answering."""

    provider: str
    model: str
    free: bool
    # Turns dropped from the context window. Silently forgetting the start of a
    # conversation is exactly the kind of thing that produces a confidently
    # wrong answer, so the user is told.
    dropped_turns: int = 0


@dataclass(frozen=True)
class Waiting:
    """Pausing for free capacity instead of escalating to a paid provider."""

    provider: str
    seconds: float
    reason: str


@dataclass(frozen=True)
class SwitchRequired:
    """No free capacity left. The stream stops here until the user approves."""

    from_provider: str
    to_provider: str
    to_model: str
    reason: str
    est_input_tokens: int
    est_output_tokens: int
    est_cost_usd: float
    conversation_cost_usd: float
    resets_at: str | None


Event = TextDelta | Usage | ProviderSelected | SwitchRequired | Waiting


class Provider(Protocol):
    def get_response_stream(self, history: list[dict]) -> Iterator[Event]: ...


# A connectivity check must not ship the whole reference sheet. Sending ~8,900
# tokens to answer "is this key valid" wastes a meaningful slice of a free
# tier's per-minute token budget.
PROBE_DOMAIN = "__probe__"
PROBE_INSTRUCTION = "Connectivity check. Reply with exactly: ok"


def latest_question(history: list[dict] | None) -> str:
    if not history:
        return ""
    for turn in reversed(history):
        if turn.get("role") == "user":
            return turn.get("content", "")
    return ""


def build_full_system_instruction(
    domain: str | None = None, history: list[dict] | None = None
) -> str:
    """System prompt, plus the discipline brief and the reference tables.

    With a discipline selected the answer gets a focused brief *and* a narrower
    reference sheet, so specificity goes up while prompt size goes down.

    With no discipline, the tables are chosen from the question itself. Shipping
    all thirteen sections every time is slow, and on a small tokens-per-minute
    tier it is larger than one request is allowed to be.
    """
    if domain == PROBE_DOMAIN:
        return PROBE_INSTRUCTION

    parts = [SYSTEM_PROMPT]
    domain_prompt = domains.get_prompt(domain)
    if domain_prompt:
        parts.append(domain_prompt)

    sections = domains.get_sections(domain)
    if sections is None:
        sections = reference_data.select_sections(latest_question(history))
    parts.append(reference_data.build(sections))
    return "\n\n".join(parts)


def text_only(stream: Iterator[Event]) -> Iterator[str]:
    """Convenience for callers that only care about the prose."""
    for event in stream:
        if isinstance(event, TextDelta):
            yield event.text


_DAILY_HINTS = (
    "perday",
    "per day",
    "per-day",
    "requests_per_day",
    "daily limit",
    "quota_metric",
)
_MINUTE_HINTS = ("perminute", "per minute", "per-minute", "requests_per_minute")


# Providers phrase the retry delay differently; catch the common shapes rather
# than defaulting to a guess that is usually far too long.
_RETRY_PATTERNS = (
    r"retry[-_ ]?after[\"'\s:]+(\d+(?:\.\d+)?)",       # retry-after: 12
    r"retry[-_ ]?delay[\"'\s:]+(\d+(?:\.\d+)?)\s*s",   # retryDelay: "24s"
    r"try again in\s+(\d+(?:\.\d+)?)\s*(?:s|sec)",     # try again in 7.5s
    r"in\s+(\d+(?:\.\d+)?)\s*(?:s|seconds)",           # ...in 30 seconds
    r"(\d+(?:\.\d+)?)\s*s(?:econds)?\b",               # bare "12s"
)


def _retry_after_from(text: str, default: float = 8.0) -> float:
    for pattern in _RETRY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return max(0.5, min(float(match.group(1)), 60.0))
    return default


def classify_rate_limit(exc: Exception, provider: str) -> LLMError:
    """Turn a provider exception into RateLimited / QuotaExceeded / LLMError.

    Both the per-minute and per-day Gemini limits surface as HTTP 429, so the
    body has to be inspected to decide whether backing off is worth it or the
    provider is done for the day.
    """
    text = str(exc)
    lowered = text.lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    is_429 = status == 429 or "429" in text or "resource_exhausted" in lowered

    if not is_429:
        return LLMError(f"{provider} API call failed: {exc}")

    if any(hint in lowered for hint in _DAILY_HINTS):
        return QuotaExceeded(f"{provider} daily free-tier quota is used up.")
    if any(hint in lowered for hint in _MINUTE_HINTS):
        return RateLimited(
            f"{provider} per-minute rate limit hit.", _retry_after_from(text)
        )
    # Ambiguous 429: treat as per-minute so a transient burst does not burn the
    # provider for the whole day. Repeated failures escalate in the caller.
    return RateLimited(f"{provider} rate limited.", _retry_after_from(text))
