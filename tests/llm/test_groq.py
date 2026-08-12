from unittest.mock import MagicMock, patch

import pytest

import config
from llm.base import LLMError, RateLimited, TextDelta, Usage
from llm.groq import GroqProvider


def _chunk(text):
    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content=text))]
    chunk.usage = None
    return chunk


def _usage_chunk(prompt_tokens, completion_tokens):
    chunk = MagicMock()
    chunk.choices = []
    chunk.usage = MagicMock(
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return chunk


@patch("llm.groq.OpenAI")
def test_uses_the_groq_base_url_with_the_groq_key(mock_openai_cls, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    mock_openai_cls.return_value.chat.completions.create.return_value = iter([])

    list(GroqProvider().get_response_stream([{"role": "user", "content": "hi"}]))

    _, kwargs = mock_openai_cls.call_args
    assert kwargs["base_url"] == config.GROQ_BASE_URL
    assert kwargs["api_key"] == "gsk-test"


@patch("llm.groq.OpenAI")
def test_yields_deltas_then_usage(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.return_value = iter(
        [_chunk("Use "), _chunk("Al 6061-T6."), _usage_chunk(1700, 450)]
    )

    events = list(GroqProvider().get_response_stream([{"role": "user", "content": "hi"}]))

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Use ", "Al 6061-T6."]
    assert events[-1] == Usage("groq", "llama-3.3-70b-versatile", 1700, 450)


@patch("llm.groq.OpenAI")
def test_per_minute_429_is_retryable(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.side_effect = Exception(
        "429 rate_limit_exceeded: requests_per_minute, retry in 8s"
    )

    with pytest.raises(RateLimited):
        list(GroqProvider().get_response_stream([{"role": "user", "content": "hi"}]))


@patch("llm.groq.OpenAI")
def test_raises_llmerror_on_api_failure(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.side_effect = Exception(
        "network error"
    )

    with pytest.raises(LLMError):
        list(GroqProvider().get_response_stream([{"role": "user", "content": "hi"}]))
