from collections.abc import Iterator
from typing import Protocol

from reference_data import REFERENCE_DATA
from system_prompt import SYSTEM_PROMPT


class LLMError(Exception):
    """Raised when an LLM provider call fails or the request is invalid."""


class Provider(Protocol):
    def get_response_stream(self, history: list[dict]) -> Iterator[str]: ...


def build_full_system_instruction() -> str:
    return f"{SYSTEM_PROMPT}\n\n{REFERENCE_DATA}"
