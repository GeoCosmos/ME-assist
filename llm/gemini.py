from collections.abc import Iterator

from google import genai
from google.genai import types

import config
from llm.base import (
    Event,
    LLMError,
    TextDelta,
    Usage,
    build_full_system_instruction,
    classify_rate_limit,
)


class GeminiProvider:
    name = "gemini"

    def get_response_stream(
        self,
        history: list[dict],
        domain: str | None = None,
        sections: tuple[str, ...] | None = None,
    ) -> Iterator[Event]:
        model = config.get_model("gemini")
        prior_turns = [
            {"role": turn["role"], "parts": [{"text": turn["content"]}]}
            for turn in history[:-1]
        ]
        latest_message = history[-1]["content"]

        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0

        try:
            client = genai.Client(api_key=config.get_api_key("gemini"))
            chat = client.chats.create(
                model=model,
                config=types.GenerateContentConfig(
                    system_instruction=build_full_system_instruction(domain, history, sections),
                ),
                history=prior_turns,
            )
            for chunk in chat.send_message_stream(latest_message):
                if chunk.text:
                    yield TextDelta(chunk.text)
                meta = getattr(chunk, "usage_metadata", None)
                if meta:
                    # Populated on the final chunk; later chunks win.
                    input_tokens = getattr(meta, "prompt_token_count", 0) or input_tokens
                    output_tokens = (
                        getattr(meta, "candidates_token_count", 0) or output_tokens
                    )
                    cached_tokens = (
                        getattr(meta, "cached_content_token_count", 0) or cached_tokens
                    )
        except LLMError:
            raise
        except Exception as exc:
            raise classify_rate_limit(exc, "Gemini") from exc

        yield Usage("gemini", model, input_tokens, output_tokens, cached_tokens)
