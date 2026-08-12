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


class OpenAIProvider:
    name = "openai"

    def get_response_stream(
        self, history: list[dict], domain: str | None = None
    ) -> Iterator[Event]:
        model = config.get_model("openai")
        messages = [{"role": "system", "content": build_full_system_instruction(domain, history)}]
        messages += [
            {"role": _ROLE_MAP[turn["role"]], "content": turn["content"]}
            for turn in history
        ]

        input_tokens = 0
        output_tokens = 0

        try:
            client = OpenAI(api_key=config.get_api_key("openai"))
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                # Without this, streamed responses report no usage at all.
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield TextDelta(delta)
                usage = getattr(chunk, "usage", None)
                if usage:
                    # Arrives in a final chunk that carries no choices.
                    input_tokens = getattr(usage, "prompt_tokens", 0) or input_tokens
                    output_tokens = (
                        getattr(usage, "completion_tokens", 0) or output_tokens
                    )
        except LLMError:
            raise
        except Exception as exc:
            raise classify_rate_limit(exc, "OpenAI") from exc

        yield Usage("openai", model, input_tokens, output_tokens)
