from unittest.mock import MagicMock, patch

import pytest

from llm.base import LLMError, QuotaExceeded, TextDelta, Usage
from llm.gemini import GeminiProvider


def _chunk(text, prompt_tokens=None, output_tokens=None):
    chunk = MagicMock()
    chunk.text = text
    if prompt_tokens is None:
        chunk.usage_metadata = None
    else:
        chunk.usage_metadata = MagicMock(
            prompt_token_count=prompt_tokens, candidates_token_count=output_tokens
        )
    return chunk


@patch("llm.gemini.genai.Client")
def test_yields_deltas_then_usage_and_passes_history(mock_client_cls):
    def fake_stream(message):
        yield _chunk("Use ")
        yield _chunk("Al 6061-T6.", prompt_tokens=1500, output_tokens=420)

    mock_chat = MagicMock()
    mock_chat.send_message_stream.side_effect = fake_stream
    mock_client_cls.return_value.chats.create.return_value = mock_chat

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    events = list(GeminiProvider().get_response_stream(history))

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Use ", "Al 6061-T6."]

    usage = events[-1]
    assert isinstance(usage, Usage)
    assert (usage.input_tokens, usage.output_tokens) == (1500, 420)
    assert usage.provider == "gemini"

    _, kwargs = mock_client_cls.return_value.chats.create.call_args
    assert "mechanical engineering assistant" in kwargs["config"].system_instruction.lower()
    assert kwargs["history"] == [
        {"role": "user", "parts": [{"text": "What material for a bracket?"}]},
        {"role": "model", "parts": [{"text": "Tell me more about the loads."}]},
    ]
    mock_chat.send_message_stream.assert_called_once_with(
        "It's a mounting bracket, light load."
    )


@patch("llm.gemini.genai.Client")
def test_raises_llmerror_on_api_failure(mock_client_cls):
    mock_client_cls.return_value.chats.create.side_effect = Exception("network error")

    with pytest.raises(LLMError):
        list(GeminiProvider().get_response_stream([{"role": "user", "content": "hi"}]))


@patch("llm.gemini.genai.Client")
def test_daily_quota_429_becomes_quota_exceeded(mock_client_cls):
    mock_client_cls.return_value.chats.create.side_effect = Exception(
        "429 RESOURCE_EXHAUSTED: quota_metric generate_content_requests_per_day"
    )

    with pytest.raises(QuotaExceeded):
        list(GeminiProvider().get_response_stream([{"role": "user", "content": "hi"}]))
