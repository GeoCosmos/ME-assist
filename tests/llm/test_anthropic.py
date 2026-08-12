from unittest.mock import MagicMock, patch

import pytest

from llm.anthropic import AnthropicProvider
from llm.base import LLMError, TextDelta, Usage


def _stream_cm(texts, input_tokens=2000, output_tokens=600):
    cm = MagicMock()
    entered = cm.__enter__.return_value
    entered.text_stream = iter(texts)
    entered.get_final_message.return_value = MagicMock(
        usage=MagicMock(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=0,
        )
    )
    return cm


@patch("llm.anthropic.Anthropic")
def test_yields_deltas_then_usage_and_passes_system_instruction(mock_anthropic_cls):
    mock_anthropic_cls.return_value.messages.stream.return_value = _stream_cm(
        ["Use ", "Al 6061-T6."]
    )

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    events = list(AnthropicProvider().get_response_stream(history))

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Use ", "Al 6061-T6."]
    assert events[-1] == Usage("anthropic", "claude-sonnet-5", 2000, 600, 0)

    _, kwargs = mock_anthropic_cls.return_value.messages.stream.call_args
    assert "mechanical engineering assistant" in kwargs["system"].lower()
    assert kwargs["messages"] == [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "assistant", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]


@patch("llm.anthropic.Anthropic")
def test_raises_llmerror_on_api_failure(mock_anthropic_cls):
    mock_anthropic_cls.return_value.messages.stream.side_effect = Exception(
        "network error"
    )

    with pytest.raises(LLMError):
        list(AnthropicProvider().get_response_stream([{"role": "user", "content": "hi"}]))
