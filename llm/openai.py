from collections.abc import Iterator

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from llm.base import LLMError, build_full_system_instruction

_ROLE_MAP = {"user": "user", "model": "assistant"}


class OpenAIProvider:
    def get_response_stream(self, history: list[dict]) -> Iterator[str]:
        messages = [{"role": "system", "content": build_full_system_instruction()}]
        messages += [
            {"role": _ROLE_MAP[turn["role"]], "content": turn["content"]}
            for turn in history
        ]

        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            stream = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMError(f"OpenAI API call failed: {exc}") from exc
