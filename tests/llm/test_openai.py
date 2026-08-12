from unittest.mock import MagicMock, patch

import pytest

from llm.base import LLMError
from llm.openai import OpenAIProvider


def _chunk(text):
    return MagicMock(choices=[MagicMock(delta=MagicMock(content=text))])


@patch("llm.openai.OpenAI")
def test_get_response_stream_yields_deltas_and_passes_system_instruction_and_history(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.return_value = iter(
        [_chunk("Use "), _chunk("Al 6061-T6.")]
    )

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    deltas = list(OpenAIProvider().get_response_stream(history))

    assert deltas == ["Use ", "Al 6061-T6."]

    _, kwargs = mock_openai_cls.return_value.chat.completions.create.call_args
    assert kwargs["messages"][0]["role"] == "system"
    assert "mechanical engineering assistant" in kwargs["messages"][0]["content"].lower()
    assert kwargs["messages"][1:] == [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "assistant", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]


@patch("llm.openai.OpenAI")
def test_get_response_stream_raises_llmerror_on_api_failure(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.side_effect = Exception("network error")

    with pytest.raises(LLMError):
        list(OpenAIProvider().get_response_stream([{"role": "user", "content": "hi"}]))
