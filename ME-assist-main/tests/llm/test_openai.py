from unittest.mock import MagicMock, patch

import pytest

from llm.base import LLMError, TextDelta, Usage
from llm.openai import OpenAIProvider


def _chunk(text):
    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content=text))]
    chunk.usage = None
    return chunk


def _usage_chunk(prompt_tokens, completion_tokens):
    chunk = MagicMock()
    chunk.choices = []
    chunk.usage = MagicMock(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt_tokens_details=MagicMock(cached_tokens=0),
    )
    return chunk


@patch("llm.openai.OpenAI")
def test_yields_deltas_then_usage_and_passes_system_instruction(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.return_value = iter(
        [_chunk("Use "), _chunk("Al 6061-T6."), _usage_chunk(1800, 500)]
    )

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    events = list(OpenAIProvider().get_response_stream(history))

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Use ", "Al 6061-T6."]
    assert events[-1] == Usage("openai", "gpt-5", 1800, 500, 0)

    _, kwargs = mock_openai_cls.return_value.chat.completions.create.call_args
    assert kwargs["messages"][0]["role"] == "system"
    assert "mechanical engineering assistant" in kwargs["messages"][0]["content"].lower()
    assert kwargs["messages"][1:] == [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "assistant", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]


@patch("llm.openai.OpenAI")
def test_usage_reporting_is_explicitly_requested(mock_openai_cls):
    """Streamed OpenAI responses report no usage unless this option is set."""
    mock_openai_cls.return_value.chat.completions.create.return_value = iter([])

    list(OpenAIProvider().get_response_stream([{"role": "user", "content": "hi"}]))

    _, kwargs = mock_openai_cls.return_value.chat.completions.create.call_args
    assert kwargs["stream_options"] == {"include_usage": True}


@patch("llm.openai.OpenAI")
def test_raises_llmerror_on_api_failure(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.side_effect = Exception(
        "network error"
    )

    with pytest.raises(LLMError):
        list(OpenAIProvider().get_response_stream([{"role": "user", "content": "hi"}]))
