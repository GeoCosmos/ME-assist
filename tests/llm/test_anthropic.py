from unittest.mock import MagicMock, patch

import pytest

from llm.anthropic import AnthropicProvider
from llm.base import LLMError


@patch("llm.anthropic.Anthropic")
def test_get_response_stream_yields_deltas_and_passes_system_instruction_and_history(mock_anthropic_cls):
    mock_stream_cm = MagicMock()
    mock_stream_cm.__enter__.return_value.text_stream = iter(["Use ", "Al 6061-T6."])
    mock_anthropic_cls.return_value.messages.stream.return_value = mock_stream_cm

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    deltas = list(AnthropicProvider().get_response_stream(history))

    assert deltas == ["Use ", "Al 6061-T6."]

    _, kwargs = mock_anthropic_cls.return_value.messages.stream.call_args
    assert "mechanical engineering assistant" in kwargs["system"].lower()
    assert kwargs["messages"] == [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "assistant", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]


@patch("llm.anthropic.Anthropic")
def test_get_response_stream_raises_llmerror_on_api_failure(mock_anthropic_cls):
    mock_anthropic_cls.return_value.messages.stream.side_effect = Exception("network error")

    with pytest.raises(LLMError):
        list(AnthropicProvider().get_response_stream([{"role": "user", "content": "hi"}]))
