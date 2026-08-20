from collections.abc import Iterator

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


def _sdk():
    """Import the SDK on first use; see llm/gemini.py for why."""
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - depends on install
        raise LLMError(
            "Claude support is not installed. Run:\n"
            "    pip install -r requirements-anthropic.txt"
        ) from exc
    return Anthropic


class AnthropicProvider:
    name = "anthropic"

    def get_response_stream(
        self,
        history: list[dict],
        domain: str | None = None,
        sections: tuple[str, ...] | None = None,
    ) -> Iterator[Event]:
        model = config.get_model("anthropic")
        messages = [
            {"role": _ROLE_MAP[turn["role"]], "content": turn["content"]}
            for turn in history
        ]

        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0

        try:
            Anthropic = _sdk()
            client = Anthropic(api_key=config.get_api_key("anthropic"))
            with client.messages.stream(
                model=model,
                max_tokens=8192,
                system=build_full_system_instruction(domain, history, sections),
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield TextDelta(text)
                # Must be read inside the context manager, after the stream drains.
                final = stream.get_final_message()
                usage = getattr(final, "usage", None)
                if usage:
                    input_tokens = getattr(usage, "input_tokens", 0) or 0
                    output_tokens = getattr(usage, "output_tokens", 0) or 0
                    cached_tokens = (
                        getattr(usage, "cache_read_input_tokens", 0) or 0
                    )
        except LLMError:
            raise
        except Exception as exc:
            raise classify_rate_limit(exc, "Anthropic") from exc

        yield Usage("anthropic", model, input_tokens, output_tokens, cached_tokens)
