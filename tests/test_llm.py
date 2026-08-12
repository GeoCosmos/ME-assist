import pytest

from llm import build_full_system_instruction, get_response_stream, LLMError


def test_build_full_system_instruction_includes_persona_and_reference_data():
    instruction = build_full_system_instruction()
    assert "mechanical engineering assistant" in instruction.lower()
    assert "6061-T6" in instruction


def test_get_response_stream_raises_llmerror_on_empty_history():
    with pytest.raises(LLMError):
        list(get_response_stream([]))


def test_get_response_stream_dispatches_to_configured_provider(monkeypatch):
    import llm

    monkeypatch.setattr(llm, "LLM_PROVIDER", "gemini")

    class FakeProvider:
        def get_response_stream(self, history):
            yield "fake output"

    monkeypatch.setitem(llm._PROVIDERS, "gemini", FakeProvider)

    result = list(get_response_stream([{"role": "user", "content": "hi"}]))

    assert result == ["fake output"]


def test_get_response_stream_raises_llmerror_on_unknown_provider(monkeypatch):
    import llm

    monkeypatch.setattr(llm, "LLM_PROVIDER", "not-a-real-provider")

    with pytest.raises(LLMError):
        list(get_response_stream([{"role": "user", "content": "hi"}]))


def test_anthropic_provider_is_registered():
    import llm
    from config import ANTHROPIC_MODEL
    from llm.anthropic import AnthropicProvider

    assert llm._PROVIDERS["anthropic"] is AnthropicProvider
    assert llm._MODELS["anthropic"] == ANTHROPIC_MODEL


def test_openai_provider_is_registered():
    import llm
    from config import OPENAI_MODEL
    from llm.openai import OpenAIProvider

    assert llm._PROVIDERS["openai"] is OpenAIProvider
    assert llm._MODELS["openai"] == OPENAI_MODEL
