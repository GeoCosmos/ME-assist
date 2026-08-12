"""Runtime configuration.

Values are read through accessor functions (not module-level constants) so that
keys and models can be changed at runtime from the settings page without
restarting the server.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

PROVIDERS = ("gemini", "groq", "anthropic", "openai")

DISPLAY_NAMES = {
    "gemini": "Gemini",
    "groq": "Groq",
    "anthropic": "Claude",
    "openai": "OpenAI",
}

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5",
}

# Suggestions for the settings panel. Not a whitelist -- any string the provider
# accepts will work -- but model ids are unguessable and a typo fails silently
# with a generic API error. Verified August 2026.
KNOWN_MODELS = {
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.6-flash",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "qwen3-32b",
    ],
    "anthropic": [
        "claude-sonnet-5",
        "claude-opus-5",
        "claude-haiku-4-5-20251001",
    ],
    "openai": [
        "gpt-5",
        "gpt-5-mini",
    ],
}

KEY_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

MODEL_ENV_VARS = {
    "gemini": "GEMINI_MODEL",
    "groq": "GROQ_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
    "openai": "OPENAI_MODEL",
}

# Free tiers first, paid providers last. Groq leads because its free daily
# allowance is roughly 50x Gemini's -- Gemini's 20/day is about two
# conversations, so leading with it would exhaust it before lunch.
DEFAULT_CHAIN = ("groq", "gemini", "openai", "anthropic")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Providers with a usable free tier, and their request-per-day allowance.
# Both are request-rate limited rather than token-metered, and both are tracked
# against a day that rolls over at midnight US/Pacific.
# Free-tier allowances.
#
# These are DEFAULTS, not truths. Published free-tier limits are model-specific
# and vary by account age, region, and verification status -- observed values
# have differed from every published figure. Treat the provider console as
# authoritative and correct these in Settings; the 429 handling is the real
# safety net, this table just avoids wasting a request to discover a limit.
#
# Values below are the ones observed in practice (August 2026):
#   gemini-2.5-flash        20 requests/day
#   llama-3.3-70b-versatile 1,000 requests/day
FREE_TIERS = {
    "gemini": {"rpd": 20, "rpm": 10, "tpm": 250_000, "tpd": 0},
    # Groq's binding limit is tokens per DAY, not requests. 1,000 requests/day
    # is irrelevant when 100,000 tokens/day runs out after ~12 large prompts.
    # This is why prompt size, not request count, is what to optimise here.
    "groq": {"rpd": 1000, "rpm": 30, "tpm": 6_000, "tpd": 100_000},
}

# Turns of conversation re-sent as context. History is re-sent in full every
# turn, so an unbounded conversation consumes a daily token budget quadratically:
# with a 100k/day cap, one long thread can eat the entire day.
DEFAULT_MAX_HISTORY_TURNS = 10

# Kept for callers that just want "the default free provider".
FREE_TIER_PROVIDER = "gemini"


def get_api_key(provider: str) -> str:
    return os.environ.get(KEY_ENV_VARS.get(provider, ""), "").strip()


def get_model(provider: str) -> str:
    if provider not in PROVIDERS:
        return ""
    return os.environ.get(
        MODEL_ENV_VARS[provider], DEFAULT_MODELS[provider]
    ).strip() or DEFAULT_MODELS[provider]


def is_configured(provider: str) -> bool:
    return bool(get_api_key(provider))


def has_free_tier(provider: str) -> bool:
    return provider in FREE_TIERS and not has_billing_enabled(provider)


def free_tier_rpd(provider: str = FREE_TIER_PROVIDER) -> int:
    default = FREE_TIERS.get(provider, {}).get("rpd", 0)
    try:
        return int(os.environ.get(f"{provider.upper()}_FREE_RPD", default))
    except ValueError:
        return default


def free_tier_rpm(provider: str = FREE_TIER_PROVIDER) -> int:
    default = FREE_TIERS.get(provider, {}).get("rpm", 0)
    try:
        return int(os.environ.get(f"{provider.upper()}_FREE_RPM", default))
    except ValueError:
        return default


def free_tier_tpm(provider: str = FREE_TIER_PROVIDER) -> int:
    default = FREE_TIERS.get(provider, {}).get("tpm", 0)
    try:
        return int(os.environ.get(f"{provider.upper()}_FREE_TPM", default))
    except ValueError:
        return default


def free_tier_tpd(provider: str = FREE_TIER_PROVIDER) -> int:
    """Free tokens per day. 0 means no known daily token cap."""
    default = FREE_TIERS.get(provider, {}).get("tpd", 0)
    try:
        return int(os.environ.get(f"{provider.upper()}_FREE_TPD", default))
    except ValueError:
        return default


def max_history_turns() -> int:
    try:
        return int(os.environ.get("MAX_HISTORY_TURNS", DEFAULT_MAX_HISTORY_TURNS))
    except ValueError:
        return DEFAULT_MAX_HISTORY_TURNS


def provider_tpm_override(provider: str) -> int | None:
    raw = os.environ.get(f"{provider.upper()}_TPM", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def provider_rpm_override(provider: str) -> int | None:
    """Explicit requests-per-minute ceiling, e.g. OPENAI_RPM=60."""
    raw = os.environ.get(f"{provider.upper()}_RPM", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def max_free_wait_seconds() -> float:
    """How long we will hold a request waiting for free capacity before
    asking the user to approve a paid provider."""
    try:
        return float(os.environ.get("MAX_FREE_WAIT_SECONDS", 25))
    except ValueError:
        return 25.0


def has_billing_enabled(provider: str) -> bool:
    """If the user pays for Gemini, there is no free tier to run out of."""
    flag = os.environ.get(f"{provider.upper()}_BILLING_ENABLED", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def get_chain() -> list[str]:
    """Ordered list of providers to try.

    LLM_CHAIN wins if set. Otherwise the chain starts with LLM_PROVIDER (for
    backward compatibility) followed by the remaining providers in default
    order. Providers without an API key are filtered out by the caller.
    """
    raw = os.environ.get("LLM_CHAIN", "").strip()
    if raw:
        chain = [p.strip().lower() for p in raw.split(",") if p.strip()]
    else:
        # Only an explicitly set LLM_PROVIDER moves to the front. Defaulting it
        # to a provider name here would silently override DEFAULT_CHAIN.
        primary = os.environ.get("LLM_PROVIDER", "").strip().lower()
        if primary:
            chain = [primary] + [p for p in DEFAULT_CHAIN if p != primary]
        else:
            chain = list(DEFAULT_CHAIN)

    seen: set[str] = set()
    ordered = []
    for provider in chain:
        if provider in PROVIDERS and provider not in seen:
            seen.add(provider)
            ordered.append(provider)
    return ordered


def primary_provider() -> str:
    chain = get_chain()
    return chain[0] if chain else "gemini"


def masked_key(provider: str) -> str:
    key = get_api_key(provider)
    if not key:
        return ""
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:5]}...{key[-4:]}"


def _quote(value: str) -> str:
    if value == "" or re.search(r"[\s#\"']", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def write_env(updates: dict[str, str]) -> None:
    """Upsert keys into .env, preserving comments and unrelated lines.

    Also updates os.environ so the change takes effect without a restart.
    """
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        return

    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        name = stripped.split("=", 1)[0].strip()
        if name in remaining:
            value = remaining.pop(name)
            out.append(f"{name}={_quote(value)}")
        else:
            out.append(line)

    for name, value in remaining.items():
        out.append(f"{name}={_quote(value)}")

    ENV_PATH.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    try:
        ENV_PATH.chmod(0o600)
    except OSError:
        pass

    for name, value in updates.items():
        if value == "":
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def reload_env() -> None:
    load_dotenv(ENV_PATH, override=True)
