from collections.abc import Iterator

from config import GEMINI_MODEL, LLM_PROVIDER
from llm.base import LLMError, build_full_system_instruction
from llm.gemini import GeminiProvider

_PROVIDERS = {
    "gemini": GeminiProvider,
}

_MODELS = {
    "gemini": GEMINI_MODEL,
}


def current_model() -> str:
    try:
        return _MODELS[LLM_PROVIDER]
    except KeyError:
        raise LLMError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}") from None


def get_response_stream(history: list[dict]) -> Iterator[str]:
    if not history:
        raise LLMError("Cannot get a response for an empty conversation.")

    try:
        provider_cls = _PROVIDERS[LLM_PROVIDER]
    except KeyError:
        raise LLMError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}") from None

    yield from provider_cls().get_response_stream(history)
