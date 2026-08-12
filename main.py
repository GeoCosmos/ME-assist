import json
from collections.abc import Iterator
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import domains
import usage as usage_ledger
import ratelimit
from llm import (
    LLMError,
    ProviderSelected,
    SwitchRequired,
    TextDelta,
    Usage,
    Waiting,
    available_providers,
    current_model,
    free_provider,
    stream_answer,
)

app = FastAPI()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: list[Message]
    conversation_id: str | None = None
    approved_provider: str | None = None
    domain: str | None = None


class SettingsRequest(BaseModel):
    keys: dict[str, str] = {}
    models: dict[str, str] = {}
    limits: dict[str, dict[str, str]] = {}
    chain: list[str] | None = None


class TestKeyRequest(BaseModel):
    provider: str


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _validate_approval(approved: str | None) -> str | None:
    """Never take the client's word for it.

    A tab left open overnight can replay an approval after quota has reset, so
    re-check that the provider is real, configured, and still the right next
    step before spending money on it.
    """
    if not approved:
        return None
    if approved not in available_providers():
        return None
    if usage_ledger.exhausted_state(approved):
        return None
    if free_provider() not in (None, approved):
        return None  # free capacity came back; use it instead
    return approved


def _stream_chat(
    history: list[dict],
    conversation_id: str | None,
    approved_provider: str | None,
    domain: str | None = None,
) -> Iterator[str]:
    try:
        for event in stream_answer(
            history, conversation_id, approved_provider, domain
        ):
            if isinstance(event, TextDelta):
                yield _sse({"delta": event.text})
            elif isinstance(event, ProviderSelected):
                yield _sse(
                    {
                        "provider": {
                            "provider": event.provider,
                            "name": config.DISPLAY_NAMES.get(
                                event.provider, event.provider
                            ),
                            "model": event.model,
                            "free": event.free,
                            "dropped_turns": event.dropped_turns,
                        }
                    }
                )
            elif isinstance(event, Waiting):
                yield _sse(
                    {
                        "waiting": {
                            "provider": event.provider,
                            "name": config.DISPLAY_NAMES.get(
                                event.provider, event.provider
                            ),
                            "seconds": event.seconds,
                            "reason": event.reason,
                        }
                    }
                )
            elif isinstance(event, Usage):
                totals = (
                    usage_ledger.conversation_totals(conversation_id)
                    if conversation_id
                    else None
                )
                yield _sse(
                    {
                        "usage": {
                            "provider": event.provider,
                            "model": event.model,
                            "input_tokens": event.input_tokens,
                            "output_tokens": event.output_tokens,
                            "conversation": totals,
                            "free_remaining": usage_ledger.free_remaining(
                                event.provider
                            ),
                        }
                    }
                )
            elif isinstance(event, SwitchRequired):
                payload = asdict(event)
                payload["to_name"] = config.DISPLAY_NAMES.get(
                    event.to_provider, event.to_provider
                )
                payload["from_name"] = config.DISPLAY_NAMES.get(
                    event.from_provider, event.from_provider
                )
                yield _sse({"switch_required": payload})
                return
        yield _sse({"done": True})
    except LLMError as exc:
        yield _sse({"error": str(exc)})


@app.post("/chat")
def chat(request: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]
    approved = _validate_approval(request.approved_provider)
    domain = request.domain if domains.is_valid(request.domain) else None
    return StreamingResponse(
        _stream_chat(history, request.conversation_id, approved, domain),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/model-info")
def model_info():
    active = free_provider() or (available_providers() or [None])[0]
    return {
        "provider": active or config.primary_provider(),
        "name": config.DISPLAY_NAMES.get(active, ""),
        "model": config.get_model(active) if active else current_model(),
        "free": active is not None and free_provider() == active,
        "chain": available_providers(),
        "free_remaining": usage_ledger.free_remaining(active) if active else None,
        "free_limit": config.free_tier_rpd(active) if active else 0,
        "tokens_remaining": usage_ledger.tokens_remaining(active) if active else None,
        "tokens_limit": config.free_tier_tpd(active) if active else 0,
        "free_tiers": usage_ledger.free_summary(),
        "resets_at": usage_ledger.next_reset().isoformat(),
        "configured": {p: config.is_configured(p) for p in config.PROVIDERS},
    }


@app.get("/domains")
def get_domains():
    return {"domains": domains.catalog()}


@app.get("/usage")
def get_usage(conversation_id: str | None = None):
    return {
        "conversation": (
            usage_ledger.conversation_totals(conversation_id)
            if conversation_id
            else None
        ),
        "today_usd": usage_ledger.spend_today(),
        "month_usd": usage_ledger.spend_this_month(),
        "free_tiers": usage_ledger.free_summary(),
        "rate_limits": ratelimit.snapshot(),
        "requests_today": {
            p: usage_ledger.requests_today(p) for p in config.PROVIDERS
        },
    }


@app.get("/settings")
def get_settings():
    return {
        "providers": [
            {
                "id": p,
                "name": config.DISPLAY_NAMES[p],
                "configured": config.is_configured(p),
                "masked_key": config.masked_key(p),
                "model": config.get_model(p),
                "default_model": config.DEFAULT_MODELS[p],
                "known_models": config.KNOWN_MODELS.get(p, []),
                "has_free_tier": config.has_free_tier(p),
                "free_remaining": usage_ledger.free_remaining(p),
                "free_limit": config.free_tier_rpd(p),
                "limits": {
                    "rpd": config.free_tier_rpd(p),
                    "rpm": config.free_tier_rpm(p),
                    "tpm": config.free_tier_tpm(p),
                    "tpd": config.free_tier_tpd(p),
                },
            }
            for p in config.PROVIDERS
        ],
        "chain": config.get_chain(),
    }


@app.post("/settings")
def save_settings(request: SettingsRequest):
    updates: dict[str, str] = {}

    for provider, key in request.keys.items():
        if provider not in config.PROVIDERS:
            continue
        key = key.strip()
        # A masked value means "unchanged" -- never write the mask back.
        if key and "..." in key and key == config.masked_key(provider):
            continue
        updates[config.KEY_ENV_VARS[provider]] = key

    for provider, model in request.models.items():
        if provider not in config.PROVIDERS:
            continue
        updates[config.MODEL_ENV_VARS[provider]] = model.strip()

    # Published free-tier limits are unreliable and account-specific, so the
    # user must be able to correct them from what their console actually says.
    for provider, limits in request.limits.items():
        if provider not in config.PROVIDERS:
            continue
        for kind in ("rpd", "rpm", "tpm", "tpd"):
            raw = str(limits.get(kind, "")).strip()
            if not raw:
                continue
            try:
                value = int(raw)
            except ValueError:
                continue
            if value >= 0:
                updates[f"{provider.upper()}_FREE_{kind.upper()}"] = str(value)

    if request.chain is not None:
        valid = [p for p in request.chain if p in config.PROVIDERS]
        if valid:
            updates["LLM_CHAIN"] = ",".join(valid)

    config.write_env(updates)

    # A new key may unblock a provider that was marked dead earlier.
    for provider in config.PROVIDERS:
        if config.is_configured(provider):
            state = usage_ledger.exhausted_state(provider)
            if state and state["reason"] == "invalid_key":
                usage_ledger.clear_exhausted(provider)

    return get_settings()


@app.post("/settings/reload")
def reload_settings():
    """Re-read .env from disk.

    Editing .env by hand while the server runs otherwise has no effect, because
    it is only loaded at import -- which looks like the change was ignored.
    """
    config.reload_env()
    return get_settings()


@app.post("/settings/test")
def test_key(request: TestKeyRequest):
    """One tiny live call, so 'it doesn't work' becomes a specific answer."""
    provider = request.provider
    if provider not in config.PROVIDERS:
        return {"ok": False, "message": f"Unknown provider {provider!r}."}
    if not config.is_configured(provider):
        return {"ok": False, "message": "No API key set."}

    from llm import _PROVIDERS
    from llm.base import PROBE_DOMAIN, QuotaExceeded, RateLimited, TextDelta as _TextDelta

    try:
        # PROBE_DOMAIN swaps the full reference sheet for a one-line prompt, so
        # a key check costs ~20 tokens instead of ~8,900.
        stream = _PROVIDERS[provider]().get_response_stream(
            [{"role": "user", "content": "Reply with the single word: ok"}],
            PROBE_DOMAIN,
        )
        for event in stream:
            if isinstance(event, _TextDelta):
                break
        return {
            "ok": True,
            "message": f"{config.DISPLAY_NAMES[provider]} responded ({config.get_model(provider)}).",
        }
    except QuotaExceeded:
        return {"ok": False, "message": "Key works, but the daily quota is used up."}
    except RateLimited:
        return {"ok": False, "message": "Key works, but you are being rate limited."}
    except LLMError as exc:
        return {"ok": False, "message": str(exc)}


@app.get("/")
def index():
    """Served explicitly with no-store so a long-open tab never shows a stale UI.

    StaticFiles' default validators let browsers hold on to the old page across
    an update, which looks exactly like the new features never shipped.
    """
    return FileResponse(
        config.BASE_DIR / "static" / "index.html",
        headers={"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"},
    )


app.mount("/", StaticFiles(directory=config.BASE_DIR / "static", html=True), name="static")
