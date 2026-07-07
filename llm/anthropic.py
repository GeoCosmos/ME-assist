from collections.abc import Iterator

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from llm.base import LLMError, build_full_system_instruction

_ROLE_MAP = {"user": "user", "model": "assistant"}


class AnthropicProvider:
    def get_response_stream(self, history: list[dict]) -> Iterator[str]:
        messages = [
            {"role": _ROLE_MAP[turn["role"]], "content": turn["content"]}
            for turn in history
        ]

        try:
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            with client.messages.stream(
                model=ANTHROPIC_MODEL,
                max_tokens=8192,
                system=build_full_system_instruction(),
                messages=messages,
            ) as stream:
                yield from stream.text_stream
        except Exception as exc:
            raise LLMError(f"Anthropic API call failed: {exc}") from exc
