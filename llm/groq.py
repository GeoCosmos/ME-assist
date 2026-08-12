from collections.abc import Iterator

from openai import OpenAI

import config
from llm.base import (
    Event,
    LLMError,
    TextDelta,
    Usage,
    build_full_system_instruction,
    classify_rate_limit,
)

_ROLE_MAP = {"user": "user", "model": "assistant"}


class GroqProvider:
    """Groq exposes an OpenAI-compatible endpoint, so the OpenAI SDK is reused
    with a different base URL.

    The free tier is metered by TOKENS, not requests: the request allowance is
    generous but the ~100k tokens/day is what actually runs out, which is why
    prompt size matters more here than call count."""

    name = "groq"

    def get_response_stream(
        self, history: list[dict], domain: str | None = None
    ) -> Iterator[Event]:
        model = config.get_model("groq")
        messages = [{"role": "system", "content": build_full_system_instruction(domain, history)}]
        messages += [
            {"role": _ROLE_MAP[turn["role"]], "content": turn["content"]}
            for turn in history
        ]

        input_tokens = 0
        output_tokens = 0

        try:
            client = OpenAI(
                api_key=config.get_api_key("groq"),
                base_url=config.GROQ_BASE_URL,
            )
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield TextDelta(delta)
                usage = getattr(chunk, "usage", None)
                if usage:
                    input_tokens = getattr(usage, "prompt_tokens", 0) or input_tokens
                    output_tokens = (
                        getattr(usage, "completion_tokens", 0) or output_tokens
                    )
        except LLMError:
            raise
        except Exception as exc:
            raise classify_rate_limit(exc, "Groq") from exc

        yield Usage("groq", model, input_tokens, output_tokens)
