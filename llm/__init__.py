from collections.abc import Iterator

from config import ANTHROPIC_MODEL, GEMINI_MODEL, LLM_PROVIDER, OPENAI_MODEL
from llm.anthropic import AnthropicProvider
from llm.base import LLMError, build_full_system_instruction
from llm.gemini import GeminiProvider
from llm.openai import OpenAIProvider

_PROVIDERS = {
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}

_MODELS = {
    "gemini": GEMINI_MODEL,
    "anthropic": ANTHROPIC_MODEL,
    "openai": OPENAI_MODEL,
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
