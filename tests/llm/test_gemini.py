from unittest.mock import MagicMock, patch

import pytest

from llm.base import LLMError
from llm.gemini import GeminiProvider


@patch("llm.gemini.genai.Client")
def test_get_response_stream_yields_deltas_and_passes_system_instruction_and_history(mock_client_cls):
    def fake_stream(message):
        chunk1 = MagicMock()
        chunk1.text = "Use "
        chunk2 = MagicMock()
        chunk2.text = "Al 6061-T6."
        yield chunk1
        yield chunk2

    mock_chat = MagicMock()
    mock_chat.send_message_stream.side_effect = fake_stream
    mock_client_cls.return_value.chats.create.return_value = mock_chat

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    deltas = list(GeminiProvider().get_response_stream(history))

    assert deltas == ["Use ", "Al 6061-T6."]

    _, kwargs = mock_client_cls.return_value.chats.create.call_args
    assert "mechanical engineering assistant" in kwargs["config"].system_instruction.lower()

    passed_history = kwargs["history"]
    assert passed_history == [
        {"role": "user", "parts": [{"text": "What material for a bracket?"}]},
        {"role": "model", "parts": [{"text": "Tell me more about the loads."}]},
    ]
    mock_chat.send_message_stream.assert_called_once_with("It's a mounting bracket, light load.")


@patch("llm.gemini.genai.Client")
def test_get_response_stream_raises_llmerror_on_api_failure(mock_client_cls):
    mock_client_cls.return_value.chats.create.side_effect = Exception("network error")

    with pytest.raises(LLMError):
        list(GeminiProvider().get_response_stream([{"role": "user", "content": "hi"}]))
