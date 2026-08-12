# Mission Control Redesign + Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the wait-for-the-whole-answer `/chat` endpoint and the "engineering log sheet" UI with real token streaming from Gemini and a "mission control" console UI (dark, sidebar with GeoCosmos logo + topic quick-launchers, live status bar).

**Architecture:** `/chat` becomes a Server-Sent-Events endpoint that always returns HTTP 200 once the stream opens; success/failure is signaled by which SSE event arrives (`delta`/`done` vs `error`), not by status code. `llm.py` gets a generator-based `get_response_stream` using `google-genai`'s `chat.send_message_stream`. The frontend is a full rewrite of `static/index.html` (still a single static file, no build step) that reads the SSE stream via `fetch` + `ReadableStream`, and must explicitly detect a stream that closes without ever sending `done`/`error` (dropped connection) so a partial answer is never shown as if it were complete.

**Tech Stack:** Python 3.11+, FastAPI (`StreamingResponse`), `google-genai`, pytest, vanilla HTML/CSS/JS.

## Global Constraints

- No RAG/document grounding, no conversation persistence beyond the browser tab, no auth, no JS framework/build step (from the original project plan — still in force).
- `GEMINI_MODEL` env var configurable via `config.py`, current default `gemini-2.5-flash`.
- `VERIFY:` flags must remain visually distinct using the `--warn` color, and that color must not be reused decoratively anywhere else.
- `/chat` HTTP status is always `200` once the SSE stream starts; failure is communicated only via an `{"error": ...}` SSE event.
- A stream that ends without ever emitting a `done` or `error` event must be treated by the frontend as its own failure case ("Response was interrupted"), never silently rendered as a complete (but short) answer.

---

### Task 1: Streaming Gemini wrapper (`llm.py`)

**Files:**
- Modify: `llm.py` (replace `get_response` with `get_response_stream`)
- Modify: `tests/test_llm.py` (replace `get_response` tests with `get_response_stream` tests)

**Interfaces:**
- Consumes: `config.GEMINI_API_KEY`, `config.GEMINI_MODEL`; `system_prompt.SYSTEM_PROMPT`; `reference_data.REFERENCE_DATA` (all unchanged from the original plan).
- Produces: `llm.LLMError(Exception)` (unchanged), `llm.build_full_system_instruction() -> str` (unchanged), `llm.get_response_stream(history: list[dict]) -> Iterator[str]` — a generator yielding text deltas as they arrive. Consumed by `main.py` (Task 2).
- Removes: `llm.get_response` (no longer called by anything once Task 2 lands — deleting it here keeps the codebase from carrying a dead code path).

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/test_llm.py` with:

```python
from unittest.mock import patch, MagicMock

import pytest

from llm import get_response_stream, build_full_system_instruction, LLMError


def test_build_full_system_instruction_includes_persona_and_reference_data():
    instruction = build_full_system_instruction()
    assert "mechanical engineering assistant" in instruction.lower()
    assert "6061-T6" in instruction


@patch("llm.genai.Client")
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
    deltas = list(get_response_stream(history))

    assert deltas == ["Use ", "Al 6061-T6."]

    _, kwargs = mock_client_cls.return_value.chats.create.call_args
    assert "mechanical engineering assistant" in kwargs["config"].system_instruction.lower()

    passed_history = kwargs["history"]
    assert passed_history == [
        {"role": "user", "parts": [{"text": "What material for a bracket?"}]},
        {"role": "model", "parts": [{"text": "Tell me more about the loads."}]},
    ]
    mock_chat.send_message_stream.assert_called_once_with("It's a mounting bracket, light load.")


@patch("llm.genai.Client")
def test_get_response_stream_raises_llmerror_on_api_failure(mock_client_cls):
    mock_client_cls.return_value.chats.create.side_effect = Exception("network error")

    with pytest.raises(LLMError):
        list(get_response_stream([{"role": "user", "content": "hi"}]))


def test_get_response_stream_raises_llmerror_on_empty_history():
    with pytest.raises(LLMError):
        list(get_response_stream([]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && pytest tests/test_llm.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_response_stream' from 'llm'` (the old `llm.py` only defines `get_response`).

- [ ] **Step 3: Rewrite `llm.py`**

Replace the full contents of `llm.py` with:

```python
from collections.abc import Iterator

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from reference_data import REFERENCE_DATA
from system_prompt import SYSTEM_PROMPT


class LLMError(Exception):
    """Raised when the Gemini API call fails or the request is invalid."""


def build_full_system_instruction() -> str:
    return f"{SYSTEM_PROMPT}\n\n{REFERENCE_DATA}"


def get_response_stream(history: list[dict]) -> Iterator[str]:
    if not history:
        raise LLMError("Cannot get a response for an empty conversation.")

    prior_turns = [
        {"role": turn["role"], "parts": [{"text": turn["content"]}]}
        for turn in history[:-1]
    ]
    latest_message = history[-1]["content"]

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        chat = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=build_full_system_instruction(),
            ),
            history=prior_turns,
        )
        for chunk in chat.send_message_stream(latest_message):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        raise LLMError(f"Gemini API call failed: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add llm.py tests/test_llm.py
git commit -m "Switch llm.py to streaming Gemini responses"
```

---

### Task 2: SSE streaming `/chat` endpoint (`main.py`)

**Files:**
- Modify: `main.py` (replace the JSON `/chat` handler with an SSE streaming one, add `/model-info`)
- Modify: `tests/test_main.py` (replace the two `/chat` tests with SSE-aware versions, add a `/model-info` test)

**Interfaces:**
- Consumes: `llm.get_response_stream(history: list[dict]) -> Iterator[str]`, `llm.LLMError` (Task 1); `config.GEMINI_MODEL` (existing).
- Produces: `POST /chat` returning `text/event-stream`, where each event is `data: <json>\n\n` and `<json>` is one of `{"delta": str}`, `{"done": true}`, `{"error": str}`. `GET /model-info` returning `{"model": str}`. `GET /` still serves `static/index.html`. Consumed by the frontend (Task 3).

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/test_main.py` with:

```python
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
```

- [ ] **Step 2: Run tests to verify the chat tests fail**

Run: `pytest tests/test_main.py -v`
Expected: `test_chat_streams_deltas_then_done` and `test_chat_streams_error_event_on_llm_failure` FAIL (current `main.py` has no `get_response_stream` import to patch — `AttributeError: <module 'main'> does not have the attribute 'get_response_stream'`); `test_model_info_returns_configured_model` FAILS with 404.

- [ ] **Step 3: Rewrite `main.py`**

Replace the full contents of `main.py` with:

```python
import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import GEMINI_MODEL
from llm import LLMError, get_response_stream

app = FastAPI()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: list[Message]


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _stream_chat(history: list[dict]) -> Iterator[str]:
    try:
        for delta in get_response_stream(history):
            yield _sse({"delta": delta})
        yield _sse({"done": True})
    except LLMError as exc:
        yield _sse({"error": str(exc)})


@app.post("/chat")
def chat(request: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]
    return StreamingResponse(_stream_chat(history), media_type="text/event-stream")


@app.get("/model-info")
def model_info():
    return {"model": GEMINI_MODEL}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: `test_chat_streams_deltas_then_done`, `test_chat_streams_error_event_on_llm_failure`, and `test_model_info_returns_configured_model` PASS. `test_root_serves_frontend` FAILS until Task 3 rewrites `static/index.html` — expected at this point, same pattern as the original plan's Task 5/6 split.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "Switch /chat to an SSE streaming endpoint, add /model-info"
```

---

### Task 3: Mission Control frontend

**Files:**
- Create: `static/geocosmos_icon.png` (copied asset)
- Modify: `static/index.html` (full rewrite)

**Interfaces:**
- Consumes: `POST /chat` SSE stream and `GET /model-info` (Task 2).

- [ ] **Step 1: Copy the GeoCosmos logo asset**

```bash
cp "/Users/alexdardarian/Desktop/geo-assist/static/geocosmos_icon.png" static/geocosmos_icon.png
```

- [ ] **Step 2: Write `static/index.html`**

Replace the full contents of `static/index.html` with:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ME-ASSIST</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0A0E12;
    --panel: #10161C;
    --grid-line: #1E2830;
    --grid-line-soft: #182028;
    --text: #C8D6DC;
    --text-dim: #5C707A;
    --text-dimmer: #3D4C56;
    --accent: #2FD8C4;
    --warn: #E8A33D;
    --warn-dim: rgba(232, 163, 61, 0.12);
    --danger: #FF5C5C;
    --font-display: 'Space Grotesk', sans-serif;
    --font-body: 'IBM Plex Sans', sans-serif;
    --font-mono: 'IBM Plex Mono', monospace;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-body);
    font-size: 15.5px;
    line-height: 1.6;
  }

  .console { display: flex; height: 100vh; }

  .ops-panel {
    width: 216px;
    flex-shrink: 0;
    background: var(--panel);
    border-right: 1px solid var(--grid-line);
    display: flex;
    flex-direction: column;
  }
  .ops-panel__brand { padding: 18px 16px 16px; border-bottom: 1px solid var(--grid-line); }
  .ops-panel__plate {
    background: #F4F2EC;
    border-radius: 3px;
    padding: 6px 10px 4px;
    display: inline-flex;
    line-height: 0;
  }
  .ops-panel__plate img { height: 18px; width: auto; display: block; }
  .ops-panel__section-label {
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.14em;
    color: var(--text-dimmer);
    padding: 16px 16px 8px;
  }
  .launchers { display: flex; flex-direction: column; gap: 2px; padding: 0 8px; }
  .launcher {
    display: flex;
    align-items: center;
    gap: 8px;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 11.5px;
    letter-spacing: 0.04em;
    text-align: left;
    padding: 9px 10px;
    border-radius: 3px;
    cursor: pointer;
    width: 100%;
  }
  .launcher::before {
    content: '';
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--text-dimmer);
    flex-shrink: 0;
  }
  .launcher:hover, .launcher:focus-visible {
    background: var(--grid-line-soft);
    color: var(--text);
    border-color: var(--grid-line);
  }
  .launcher:hover::before, .launcher:focus-visible::before { background: var(--accent); }
  .launcher:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }

  .ops-panel__footer {
    margin-top: auto;
    padding: 14px 16px 18px;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    color: var(--text-dimmer);
  }

  .main { flex: 1; display: flex; flex-direction: column; min-width: 0; }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 11px 20px;
    border-bottom: 1px solid var(--grid-line);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.06em;
    color: var(--text-dim);
  }
  .status-bar__toggle {
    display: none;
    background: none;
    border: 1px solid var(--grid-line);
    color: var(--text-dim);
    border-radius: 3px;
    width: 28px;
    height: 28px;
    cursor: pointer;
    font-size: 13px;
  }
  .status-bar__name {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.01em;
    color: var(--text);
    margin-right: auto;
  }
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-dimmer);
    display: inline-block;
    margin-right: 6px;
  }
  .status-live .status-dot {
    background: var(--accent);
    box-shadow: 0 0 6px var(--accent);
    animation: pulse 1.6s ease-in-out infinite;
  }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
  .status-live { color: var(--accent); }

  .log { flex: 1; overflow-y: auto; padding: 22px 20px 8px; }
  .log__empty { color: var(--text-dim); font-size: 14.5px; max-width: 46ch; padding-top: 40px; }

  .entry { margin-bottom: 26px; }
  .entry__meta {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding-bottom: 6px;
    margin-bottom: 10px;
    border-bottom: 1px solid var(--grid-line);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--text-dim);
  }
  .entry--query .entry__label { color: var(--accent); }
  .entry--error .entry__label { color: var(--danger); }
  .entry--error { border-left: 2px solid var(--danger); padding-left: 14px; }

  .entry__body p { margin: 0 0 12px; }
  .entry__body p:last-child { margin-bottom: 0; }
  .entry__body code {
    font-family: var(--font-mono);
    font-size: 0.9em;
    background: var(--panel);
    padding: 1px 5px;
    border-radius: 3px;
  }
  .entry__body ul { margin: 0 0 12px; padding-left: 20px; }
  .entry__body .flag {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    background: var(--warn-dim);
    border-left: 2px solid var(--warn);
    color: var(--warn);
    padding: 8px 12px;
    font-family: var(--font-mono);
    font-size: 13px;
    margin: 12px 0;
    border-radius: 0 3px 3px 0;
  }

  .cursor {
    display: inline-block;
    width: 7px;
    height: 15px;
    background: var(--accent);
    margin-left: 2px;
    vertical-align: text-bottom;
    animation: blink 1s step-start infinite;
  }
  @keyframes blink { 50% { opacity: 0; } }

  .sr-only {
    position: absolute;
    width: 1px; height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }

  @media (prefers-reduced-motion: reduce) {
    .status-live .status-dot, .cursor { animation: none; }
  }

  .input-bar {
    display: flex;
    gap: 10px;
    align-items: flex-end;
    padding: 14px 20px;
    border-top: 1px solid var(--grid-line);
    background: var(--bg);
  }
  .input-bar__field {
    flex: 1;
    resize: none;
    max-height: 200px;
    background: var(--panel);
    color: var(--text);
    border: 1px solid var(--grid-line);
    border-radius: 4px;
    padding: 10px 12px;
    font-family: var(--font-body);
    font-size: 14.5px;
    line-height: 1.4;
  }
  .input-bar__field:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  .input-bar__send {
    background: var(--accent);
    color: #04201C;
    border: none;
    border-radius: 4px;
    width: 38px;
    height: 38px;
    font-size: 15px;
    cursor: pointer;
    flex-shrink: 0;
    font-weight: 700;
  }
  .input-bar__send:hover { filter: brightness(1.1); }
  .input-bar__send:focus-visible { outline: 2px solid var(--text); outline-offset: 2px; }

  .ops-panel__scrim { display: none; }
  @media (max-width: 640px) {
    .status-bar__toggle { display: inline-block; }
    .ops-panel {
      position: fixed;
      inset: 0 25% 0 0;
      z-index: 20;
      transform: translateX(-100%);
      transition: transform 0.2s ease;
    }
    .ops-panel.is-open { transform: translateX(0); }
    .ops-panel__scrim {
      display: block;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.5);
      z-index: 10;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s ease;
    }
    .ops-panel__scrim.is-open { opacity: 1; pointer-events: auto; }
    .status-bar { padding: 10px 14px; gap: 12px; font-size: 10.5px; }
    .log { padding: 18px 14px 8px; }
    .input-bar { padding: 12px 14px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .ops-panel { transition: none; }
    .ops-panel__scrim { transition: none; }
  }
</style>
</head>
<body>
  <div class="console">
    <div class="ops-panel__scrim" id="scrim"></div>
    <aside class="ops-panel" id="ops-panel">
      <div class="ops-panel__brand">
        <span class="ops-panel__plate"><img src="/geocosmos_icon.png" alt="GeoCosmos"></span>
      </div>
      <div class="ops-panel__section-label">QUICK LAUNCH</div>
      <div class="launchers" id="launchers">
        <button type="button" class="launcher" data-question="How do I calculate the reaction forces on this bracket?">STATICS / DYNAMICS</button>
        <button type="button" class="launcher" data-question="What material would you recommend for this part, and why?">MATERIALS</button>
        <button type="button" class="launcher" data-question="How will this component behave under thermal cycling in orbit?">THERMAL</button>
        <button type="button" class="launcher" data-question="What layup would you use for this panel, and what failure theory applies?">COMPOSITES</button>
        <button type="button" class="launcher" data-question="What's the expected response of this bracket to launch vibration?">VIBRATIONS</button>
        <button type="button" class="launcher" data-question="What GD&amp;T callouts should I use on this drawing?">GD&amp;T</button>
        <button type="button" class="launcher" data-question="What fastener size and torque should I use here?">FASTENERS</button>
        <button type="button" class="launcher" data-question="Is this part design-for-manufacturability friendly?">MANUFACTURING</button>
      </div>
      <div class="ops-panel__footer">ME-ASSIST&nbsp;/&nbsp;GEOCOSMOS</div>
    </aside>

    <div class="main">
      <header class="status-bar">
        <button type="button" class="status-bar__toggle" id="panel-toggle" aria-label="Toggle quick launch panel">&#9776;</button>
        <span class="status-bar__name">ME-ASSIST</span>
        <span id="model-label">MODEL: &mdash;</span>
        <span id="status-label">IDLE</span>
        <span id="latency-label"></span>
      </header>

      <main class="log" id="log" aria-live="polite">
        <div class="log__empty" id="empty-state">
          <p>No entries yet. Ask a mechanical engineering question below &mdash; statics, materials, thermal, composites, tolerancing, whatever you've got. Or pick a quick launch topic from the panel.</p>
        </div>
      </main>

      <form class="input-bar" id="input-form">
        <textarea id="input" class="input-bar__field" placeholder="Ask a mechanical engineering question&hellip;" rows="1" required></textarea>
        <button type="submit" class="input-bar__send" aria-label="Send">&#10148;</button>
      </form>
    </div>
  </div>

<script>
  const log = document.getElementById('log');
  const emptyState = document.getElementById('empty-state');
  const form = document.getElementById('input-form');
  const input = document.getElementById('input');
  const statusLabel = document.getElementById('status-label');
  const latencyLabel = document.getElementById('latency-label');
  const modelLabel = document.getElementById('model-label');
  const opsPanel = document.getElementById('ops-panel');
  const scrim = document.getElementById('scrim');
  const panelToggle = document.getElementById('panel-toggle');
  const launchers = document.getElementById('launchers');

  let history = [];
  let entryIndex = 0;

  fetch('/model-info')
    .then((res) => res.json())
    .then((data) => { modelLabel.textContent = `MODEL: ${data.model}`; })
    .catch(() => { modelLabel.textContent = 'MODEL: unknown'; });

  function pad(n) {
    return String(n).padStart(3, '0');
  }

  function formatBody(text) {
    const escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    const withInline = escaped
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');

    const lines = withInline.split('\n');
    const htmlParts = [];
    let listBuffer = [];

    const flushList = () => {
      if (listBuffer.length) {
        htmlParts.push(`<ul>${listBuffer.map((li) => `<li>${li}</li>`).join('')}</ul>`);
        listBuffer = [];
      }
    };

    for (const rawLine of lines) {
      const trimmed = rawLine.trim();
      if (!trimmed) {
        flushList();
        continue;
      }
      if (trimmed.startsWith('VERIFY:')) {
        flushList();
        htmlParts.push(
          `<div class="flag"><span aria-hidden="true">&#9888;</span>${trimmed.slice(7).trim()}</div>`
        );
      } else if (trimmed.startsWith('- ')) {
        listBuffer.push(trimmed.slice(2));
      } else {
        flushList();
        htmlParts.push(`<p>${trimmed}</p>`);
      }
    }
    flushList();
    return htmlParts.join('');
  }

  function appendEntry(role, index, label, bodyHTML) {
    if (emptyState && emptyState.parentNode) emptyState.remove();
    const article = document.createElement('article');
    article.className = `entry entry--${role}`;
    article.innerHTML = `
      <div class="entry__meta">
        <span class="entry__index">${pad(index)}</span>
        <span class="entry__label">${label}</span>
      </div>
      <div class="entry__body">${bodyHTML}</div>
    `;
    log.appendChild(article);
    log.scrollTop = log.scrollHeight;
    return article;
  }

  function setStatus(state) {
    if (state === 'transmitting') {
      statusLabel.innerHTML = '<span class="status-dot"></span>TRANSMITTING';
      statusLabel.classList.add('status-live');
    } else {
      statusLabel.textContent = 'IDLE';
      statusLabel.classList.remove('status-live');
    }
  }

  function parseSseBuffer(buffer, onEvent) {
    let sepIndex;
    while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      if (rawEvent.startsWith('data: ')) {
        onEvent(JSON.parse(rawEvent.slice(6)));
      }
    }
    return buffer;
  }

  async function streamChat(requestHistory, onDelta) {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ history: requestHistory }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let sawDone = false;
    let sawError = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = parseSseBuffer(buffer, (payload) => {
        if (payload.delta) {
          fullText += payload.delta;
          onDelta(fullText);
        } else if (payload.done) {
          sawDone = true;
        } else if (payload.error) {
          sawError = payload.error;
        }
      });
    }

    if (sawError) {
      return { ok: false, error: sawError };
    }
    if (!sawDone) {
      return { ok: false, error: 'Response was interrupted. Please try again.' };
    }
    return { ok: true, text: fullText };
  }

  function openPanel() {
    opsPanel.classList.add('is-open');
    scrim.classList.add('is-open');
  }
  function closePanel() {
    opsPanel.classList.remove('is-open');
    scrim.classList.remove('is-open');
  }
  panelToggle.addEventListener('click', () => {
    opsPanel.classList.contains('is-open') ? closePanel() : openPanel();
  });
  scrim.addEventListener('click', closePanel);

  launchers.addEventListener('click', (e) => {
    const btn = e.target.closest('.launcher');
    if (!btn) return;
    input.value = btn.dataset.question;
    input.dispatchEvent(new Event('input'));
    input.focus();
    closePanel();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    entryIndex += 1;
    appendEntry('query', entryIndex, 'QUERY', formatBody(text));
    history.push({ role: 'user', content: text });
    input.value = '';
    input.style.height = 'auto';

    setStatus('transmitting');
    const startedAt = performance.now();
    const responseArticle = appendEntry('response', entryIndex, 'RESPONSE', '<p><span class="cursor"></span></p>');
    const responseBody = responseArticle.querySelector('.entry__body');

    const result = await streamChat(history, (partialText) => {
      responseBody.innerHTML = formatBody(partialText) + '<span class="cursor"></span>';
      log.scrollTop = log.scrollHeight;
    });

    setStatus('idle');

    if (!result.ok) {
      responseArticle.remove();
      appendEntry('error', entryIndex, 'ERROR', formatBody(result.error));
      return;
    }

    responseBody.innerHTML = formatBody(result.text);
    history.push({ role: 'model', content: result.text });
    const elapsedSeconds = ((performance.now() - startedAt) / 1000).toFixed(1);
    latencyLabel.textContent = `LAT: ${elapsedSeconds}s`;
  });

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
</script>
</body>
</html>
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS, including `test_root_serves_frontend` (the page still contains the literal text "ME-ASSIST" in the status bar).

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/geocosmos_icon.png
git commit -m "Rewrite frontend as a mission-control console with streaming"
```

---

### Task 4: Docs fix and manual end-to-end verification

**Files:**
- Modify: `README.md` (fix the documented default model, which is out of date)

- [ ] **Step 1: Fix the stale default-model line in `README.md`**

Find this line (left over from before the default was changed):

```
# optional: export GEMINI_MODEL="gemini-2.5-pro" (this is the default)
```

Replace it with:

```
# optional: export GEMINI_MODEL="gemini-2.5-flash" (this is the default)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Fix stale GEMINI_MODEL default in README"
```

- [ ] **Step 3: Manual end-to-end verification**

With a real `GEMINI_API_KEY` exported, run `uvicorn main:app --reload --port 8000` and open `http://127.0.0.1:8000`. Confirm:

- The status bar shows `ME-ASSIST`, `MODEL: gemini-2.5-flash` (or whatever `GEMINI_MODEL` is set to), and `IDLE` before any message is sent.
- The GeoCosmos logo appears on its light nameplate chip at the top of the left ops panel.
- Clicking each of the 8 quick-launch buttons (Statics/Dynamics, Materials, Thermal, Composites, Vibrations, GD&T, Fasteners, Manufacturing) fills the input with that topic's starter question, without sending it.
- Sending a message flips the status bar to `TRANSMITTING` (pulsing dot) and the response text visibly appears incrementally, word-by-word/chunk-by-chunk, with a blinking cursor at the end of the in-progress text — not the whole answer pasted in at once.
- Once the response finishes, the status bar returns to `IDLE`, the cursor disappears, and a `LAT: <n>s` readout appears.
- Asking a flight-critical structural question (e.g. "what's the margin of safety on a 5mm 6061-T6 bracket under a 200N load?") produces a response containing an amber-highlighted `VERIFY:` flag box, distinct from the surrounding text.
- Temporarily setting `GEMINI_API_KEY` to an invalid value and restarting the server, then sending a message, produces a visible red-bordered `ERROR` entry (via the SSE `error` event) rather than a silent failure, a crash, or a partial answer with no indication anything went wrong.
- **Dropped-connection case (no clean `done`/`error` at all):** send a message, and while the response is still streaming (status bar reads `TRANSMITTING`, text is still appearing), kill the `uvicorn` process (`Ctrl+C` in its terminal) before it finishes. Confirm the browser shows a red-bordered `ERROR` entry reading "Response was interrupted. Please try again." — not a silently truncated response with no error shown, and not a JS console error with no UI feedback.
- Resizing the browser below 640px width hides the ops panel by default; the hamburger toggle in the status bar opens it as a slide-over drawer over the chat, and tapping outside it (the scrim) or picking a launcher closes it again. No horizontal scrolling anywhere at this width.
- Tabbing through the page shows a visible focus outline on quick-launcher buttons, the input field, and the send button.
