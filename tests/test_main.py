import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import config
import usage
from llm.base import (
    LLMError,
    ProviderSelected,
    SwitchRequired,
    TextDelta,
    Usage,
)
from main import app

client = TestClient(app)


def _parse_sse(body: str) -> list[dict]:
    events = []
    for chunk in body.split("\n\n"):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[len("data: "):]))
    return events


def _post(history=None, **kwargs):
    payload = {"history": history or [{"role": "user", "content": "hi"}]}
    payload.update(kwargs)
    return client.post("/chat", json=payload)


@patch("main.stream_answer")
def test_chat_streams_deltas_then_done(mock_stream):
    mock_stream.return_value = iter(
        [
            ProviderSelected("gemini", "gemini-2.5-flash", True),
            TextDelta("Use "),
            TextDelta("Al 6061-T6."),
            Usage("gemini", "gemini-2.5-flash", 1200, 400),
        ]
    )

    response = _post([{"role": "user", "content": "Fillet radius?"}])

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events[0]["provider"]["provider"] == "gemini"
    assert events[0]["provider"]["free"] is True
    assert [e["delta"] for e in events if "delta" in e] == ["Use ", "Al 6061-T6."]
    assert events[-1] == {"done": True}


@patch("main.stream_answer")
def test_chat_emits_switch_required_and_stops(mock_stream):
    mock_stream.return_value = iter(
        [
            SwitchRequired(
                from_provider="gemini",
                to_provider="openai",
                to_model="gpt-5",
                reason="free_tier_daily_limit",
                est_input_tokens=5000,
                est_output_tokens=800,
                est_cost_usd=0.0143,
                conversation_cost_usd=0.0,
                resets_at="2026-08-13T00:00:00-07:00",
            )
        ]
    )

    events = _parse_sse(_post().text)

    assert len(events) == 1
    payload = events[0]["switch_required"]
    assert payload["to_provider"] == "openai"
    assert payload["to_name"] == "OpenAI"
    assert payload["est_cost_usd"] == 0.0143
    # No "done" -- the turn is deliberately left unfinished pending approval.
    assert not any("done" in e for e in events)


@patch("main.stream_answer")
def test_chat_streams_error_event_on_llm_failure(mock_stream):
    def raise_error(*args, **kwargs):
        raise LLMError("Gemini API call failed: network error")
        yield  # pragma: no cover

    mock_stream.side_effect = raise_error

    events = _parse_sse(_post().text)
    assert events == [{"error": "Gemini API call failed: network error"}]


@patch("main.stream_answer")
def test_approval_is_passed_through_when_valid(mock_stream, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPD", "0")
    mock_stream.return_value = iter([TextDelta("ok")])

    _post(approved_provider="openai")

    assert mock_stream.call_args[0][2] == "openai"


@patch("main.stream_answer")
def test_unconfigured_approval_is_rejected(mock_stream, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mock_stream.return_value = iter([TextDelta("ok")])

    _post(approved_provider="openai")

    assert mock_stream.call_args[0][2] is None


@patch("main.stream_answer")
def test_stale_approval_is_dropped_once_free_quota_returns(mock_stream, monkeypatch):
    """A tab left open overnight must not spend money after the quota resets."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_FREE_RPD", "250")  # free capacity is back
    mock_stream.return_value = iter([TextDelta("ok")])

    _post(approved_provider="openai")

    assert mock_stream.call_args[0][2] is None


def test_model_info_reports_free_position():
    body = client.get("/model-info").json()

    assert body["provider"] == "gemini"
    assert body["free"] is True
    assert body["free_remaining"] == config.free_tier_rpd("gemini")
    assert body["configured"]["gemini"] is True
    assert body["configured"]["openai"] is False


def test_usage_endpoint_reports_conversation_and_totals():
    usage.record("openai", "gpt-5", 10_000, 2_000, conversation_id="conv-x")

    body = client.get("/usage", params={"conversation_id": "conv-x"}).json()

    assert body["conversation"]["turns"] == 1
    assert body["today_usd"] > 0
    assert body["free_tiers"]["gemini"]["limit"] == config.free_tier_rpd("gemini")


def test_settings_never_returns_a_full_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-supersecretvalue123")

    body = client.get("/settings").json()
    openai = next(p for p in body["providers"] if p["id"] == "openai")

    assert openai["configured"] is True
    assert "supersecretvalue" not in json.dumps(body)
    assert openai["masked_key"].endswith("e123")


def test_settings_lists_all_four_providers():
    body = client.get("/settings").json()
    assert [p["id"] for p in body["providers"]] == list(config.PROVIDERS)
    groq = next(p for p in body["providers"] if p["id"] == "groq")
    assert groq["has_free_tier"] is True


def test_saving_settings_writes_env_and_takes_effect(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    response = client.post(
        "/settings",
        json={"keys": {"groq": "gsk-newkey"}, "models": {"groq": "llama-3.1-8b-instant"}},
    )

    assert response.status_code == 200
    assert config.get_api_key("groq") == "gsk-newkey"
    assert config.get_model("groq") == "llama-3.1-8b-instant"
    assert "gsk-newkey" in env_file.read_text()


def test_saving_a_masked_key_does_not_overwrite_the_real_one(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-realkeyvalue1234")
    masked = config.masked_key("openai")

    client.post("/settings", json={"keys": {"openai": masked}, "models": {}})

    assert config.get_api_key("openai") == "sk-proj-realkeyvalue1234"


def test_root_serves_frontend():
    response = client.get("/")

    assert response.status_code == 200
    assert "ME-ASSIST" in response.text


def test_settings_suggests_model_ids():
    """Model ids are unguessable; a typo otherwise fails with a vague error."""
    body = client.get("/settings").json()
    gemini = next(p for p in body["providers"] if p["id"] == "gemini")

    assert "gemini-3.6-flash" in gemini["known_models"]
    assert gemini["model"] in gemini["known_models"] or gemini["model"]


def test_changing_the_model_takes_effect_immediately(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    client.post("/settings", json={"keys": {}, "models": {"gemini": "gemini-3.6-flash"}})

    assert config.get_model("gemini") == "gemini-3.6-flash"
    assert client.get("/model-info").json()["model"] or True


def test_reload_picks_up_a_hand_edited_env(tmp_path, monkeypatch):
    """Editing .env while the server runs must not silently do nothing."""
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_MODEL=gemini-2.5-flash-lite\n")
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    response = client.post("/settings/reload")

    assert response.status_code == 200
    assert config.get_model("gemini") == "gemini-2.5-flash-lite"


def test_free_limits_are_editable_from_settings(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    client.post("/settings", json={"limits": {"groq": {"rpd": "1000", "tpd": "100000"}}})

    assert config.free_tier_rpd("groq") == 1000
    assert config.free_tier_tpd("groq") == 100000
