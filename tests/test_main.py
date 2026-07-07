import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from config import GEMINI_MODEL
from main import app
from llm import LLMError

client = TestClient(app)


def _parse_sse(body: str) -> list[dict]:
    events = []
    for chunk in body.split("\n\n"):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[len("data: "):]))
    return events


@patch("main.get_response_stream")
def test_chat_streams_deltas_then_done(mock_get_response_stream):
    mock_get_response_stream.return_value = iter(["Use ", "Al 6061-T6."])

    response = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "Fillet radius for a stress concentration?"}]},
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events == [
        {"delta": "Use "},
        {"delta": "Al 6061-T6."},
        {"done": True},
    ]
    mock_get_response_stream.assert_called_once_with(
        [{"role": "user", "content": "Fillet radius for a stress concentration?"}]
    )


@patch("main.get_response_stream")
def test_chat_streams_error_event_on_llm_failure(mock_get_response_stream):
    def raise_error(history):
        raise LLMError("Gemini API call failed: network error")
        yield  # pragma: no cover - makes this a generator function

    mock_get_response_stream.side_effect = raise_error

    response = client.post("/chat", json={"history": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events == [{"error": "Gemini API call failed: network error"}]


def test_model_info_returns_configured_model():
    response = client.get("/model-info")

    assert response.status_code == 200
    assert response.json() == {"model": GEMINI_MODEL}


def test_root_serves_frontend():
    response = client.get("/")

    assert response.status_code == 200
    assert "ME-ASSIST" in response.text
