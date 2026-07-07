from collections.abc import Iterator

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from reference_data import REFERENCE_DATA
from system_prompt import SYSTEM_PROMPT


class LLMError(Exception):
    """Raised when the Gemini API call fails or the request is invalid."""


def build_full_system_instruction() -> str:
    return f"{SYSTEM_PROMPT}\n\n{REFERENCE_DATA}"


def get_response_stream(history: list[dict]) -> Iterator[str]:
    if not history:
        raise LLMError("Cannot get a response for an empty conversation.")

    prior_turns = [
        {"role": turn["role"], "parts": [{"text": turn["content"]}]}
        for turn in history[:-1]
    ]
    latest_message = history[-1]["content"]

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        chat = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=build_full_system_instruction(),
            ),
            history=prior_turns,
        )
        for chunk in chat.send_message_stream(latest_message):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        raise LLMError(f"Gemini API call failed: {exc}") from exc
