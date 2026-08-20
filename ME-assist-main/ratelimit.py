"""Client-side per-minute pacing.

Free tiers are limited by requests-per-minute as well as per-day, and the
per-minute ceiling is the one a couple of active users actually hit. Waiting for
a 429 to discover this is wasteful and -- worse -- a transient 60-second blip
would otherwise escalate into a "this costs money" prompt while the daily free
quota is still almost untouched.

So requests are paced locally: we know the published RPM for each free tier, we
count our own recent attempts, and we step aside *before* sending. Observed 429s
feed back in as a cooldown, because the local count can drift when a key is
shared with another project.

State is in-memory. The window is only 60 seconds, so losing it on restart
costs at most one wasted 429.
"""

import threading
import time
from collections import defaultdict, deque

import config

WINDOW_SECONDS = 60.0

# Small margin so we stop just short of the published ceiling rather than
# discovering it. Also absorbs clock skew against the provider's own window.
SAFETY_MARGIN = 1

# A request whose prompt alone exceeds the per-minute token budget can never
# succeed on that provider, no matter how long we wait.
INFEASIBLE = float("inf")

_lock = threading.Lock()
_attempts: dict[str, deque[float]] = defaultdict(deque)
_tokens: dict[str, deque[tuple[float, int]]] = defaultdict(deque)
_cooldowns: dict[str, float] = {}


def _limit(provider: str) -> int:
    """Requests per minute for this provider, or 0 for 'no known limit'."""
    override = config.provider_rpm_override(provider)
    if override is not None:
        return override
    if config.has_free_tier(provider):
        return config.free_tier_rpm(provider)
    # Paid tiers have limits too, but they are account-specific and far higher.
    # Pace only when the user tells us to.
    return 0


def _tpm_limit(provider: str) -> int:
    override = config.provider_tpm_override(provider)
    if override is not None:
        return override
    if config.has_free_tier(provider):
        return config.free_tier_tpm(provider)
    return 0


def _prune(provider: str, now: float) -> deque[float]:
    stamps = _attempts[provider]
    while stamps and now - stamps[0] >= WINDOW_SECONDS:
        stamps.popleft()
    return stamps


def _prune_tokens(provider: str, now: float) -> deque[tuple[float, int]]:
    stamps = _tokens[provider]
    while stamps and now - stamps[0][0] >= WINDOW_SECONDS:
        stamps.popleft()
    return stamps


def note_tokens(provider: str, count: int, now: float | None = None) -> None:
    """Record tokens spent against the per-minute budget."""
    if count <= 0:
        return
    now = time.time() if now is None else now
    with _lock:
        _prune_tokens(provider, now)
        _tokens[provider].append((now, count))


def token_wait(provider: str, needed: int, now: float | None = None) -> float:
    """Seconds until `needed` tokens fit in the per-minute budget.

    Returns INFEASIBLE if the request could never fit, which is a different
    problem from being busy and needs a different message.
    """
    now = time.time() if now is None else now
    limit = _tpm_limit(provider)
    if limit <= 0 or needed <= 0:
        return 0.0
    if needed > limit:
        return INFEASIBLE

    with _lock:
        stamps = _prune_tokens(provider, now)
        used = sum(count for _, count in stamps)
        if used + needed <= limit:
            return 0.0
        freed = 0
        for ts, count in stamps:
            freed += count
            if used - freed + needed <= limit:
                return WINDOW_SECONDS - (now - ts) + 0.25
    return INFEASIBLE


def note_attempt(provider: str, now: float | None = None) -> None:
    """Record that a request is about to be sent."""
    now = time.time() if now is None else now
    with _lock:
        _prune(provider, now)
        _attempts[provider].append(now)


def cooldown(provider: str, seconds: float, now: float | None = None) -> None:
    """Park a provider after an observed 429, for the time it asked for."""
    now = time.time() if now is None else now
    with _lock:
        _cooldowns[provider] = max(_cooldowns.get(provider, 0.0), now + seconds)


def clear_cooldown(provider: str) -> None:
    with _lock:
        _cooldowns.pop(provider, None)


def wait_needed(
    provider: str, now: float | None = None, tokens: int = 0
) -> float:
    """Seconds to wait before this provider can take a request. 0 means now.

    Accounts for the observed-429 cooldown, the requests-per-minute window, and
    the tokens-per-minute budget, and returns the worst of the three.
    """
    now = time.time() if now is None else now
    token_delay = token_wait(provider, tokens, now)
    if token_delay == INFEASIBLE:
        return INFEASIBLE

    with _lock:
        until = _cooldowns.get(provider)
        cooldown_wait = max(0.0, until - now) if until else 0.0
        if until and cooldown_wait <= 0:
            _cooldowns.pop(provider, None)

        limit = _limit(provider)
        if limit <= 0:
            return max(cooldown_wait, token_delay)

        stamps = _prune(provider, now)
        usable = max(1, limit - SAFETY_MARGIN)
        if len(stamps) < usable:
            return max(cooldown_wait, token_delay)

        # The oldest attempt in the window has to age out before a slot frees.
        window_wait = WINDOW_SECONDS - (now - stamps[0]) + 0.25
        return max(cooldown_wait, window_wait, token_delay)


def snapshot() -> dict[str, dict]:
    """Current pacing position, for diagnostics and the settings panel."""
    now = time.time()
    out = {}
    for provider in config.PROVIDERS:
        with _lock:
            used = len(_prune(provider, now))
            tokens_used = sum(c for _, c in _prune_tokens(provider, now))
        out[provider] = {
            "limit_rpm": _limit(provider),
            "used_in_window": used,
            "limit_tpm": _tpm_limit(provider),
            "tokens_in_window": tokens_used,
            "wait_seconds": round(wait_needed(provider, now), 1),
        }
    return out


def fits_token_budget(provider: str, tokens: int) -> bool:
    """False when a prompt this size can never clear the per-minute budget."""
    return token_wait(provider, tokens) != INFEASIBLE


def reset() -> None:
    with _lock:
        _attempts.clear()
        _tokens.clear()
        _cooldowns.clear()
