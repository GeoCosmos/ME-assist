# ME Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a chat web app that lets Geocosmos engineers ask mechanical engineering questions and get rigorous, master's-level-or-better answers from Gemini, with a distinctive "engineering log sheet" UI.

**Architecture:** A stateless FastAPI backend with a single `POST /chat` endpoint that forwards the full conversation to the Gemini API with a fixed system prompt + curated reference data, plus a single static HTML/CSS/JS page (no framework, no build step) served by the same app. No database, no auth, no RAG.

**Tech Stack:** Python 3.11+, FastAPI, `google-generativeai`, pytest, vanilla HTML/CSS/JS.

## Global Constraints

- No RAG / document grounding — answers come from the model's own knowledge.
- No conversation persistence — history lives only in the browser tab.
- No auth, no multi-user accounts.
- No fine-tuning or custom model training.
- No JS framework, no build step for the frontend — plain HTML/CSS/JS only.
- Gemini model name must be configurable via the `GEMINI_MODEL` env var (default `gemini-2.5-pro`) — model choice matters more for answer quality than prompt wording.
- The system prompt must instruct the model to never simplify based on how casually a question is phrased, to show its work, to cover statics/dynamics, mechanics of materials, thermodynamics/heat transfer, composites, vibrations, materials science, GD&T/tolerancing, fasteners, and manufacturing/DFM without letting any of them lag in depth, to be satellite-aware but not satellite-only, and to flag flight-critical/load-bearing conclusions with a literal `VERIFY:` prefix line naming what needs sign-off.
- The frontend must visually distinguish `VERIFY:` flags from normal response text.

---

### Task 1: Project scaffolding & config

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `conftest.py`
- Create: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.GEMINI_API_KEY: str`, `config.GEMINI_MODEL: str` — read fresh from env vars at import time; later tasks (`llm.py`) import these directly.

- [ ] **Step 1: Create the directory structure and non-Python files**

```bash
mkdir -p tests static
```

`requirements.txt`:
```
fastapi
uvicorn
google-generativeai
pydantic
pytest
httpx
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
venv/
.venv/
```

`conftest.py` (empty file at project root — makes pytest add the project root to `sys.path` so test modules can `import config`, `import llm`, etc.):
```python
```

- [ ] **Step 2: Write the failing test for config defaults**

`tests/test_config.py`:
```python
import importlib


def test_default_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    import config
    importlib.reload(config)
    assert config.GEMINI_MODEL == "gemini-2.5-pro"


def test_model_reads_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    import config
    importlib.reload(config)
    assert config.GEMINI_MODEL == "gemini-custom"


def test_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    import config
    importlib.reload(config)
    assert config.GEMINI_API_KEY == "test-key-123"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 4: Write config.py**

`config.py`:
```python
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore conftest.py config.py tests/test_config.py
git commit -m "Add project scaffolding and config"
```

---

### Task 2: Reference data (engineering cheat-sheet)

**Files:**
- Create: `reference_data.py`
- Test: `tests/test_reference_data.py`

**Interfaces:**
- Produces: `reference_data.REFERENCE_DATA: str` — consumed by `llm.py` (Task 4) as part of the Gemini system instruction.

- [ ] **Step 1: Write the failing test**

`tests/test_reference_data.py`:
```python
from reference_data import REFERENCE_DATA


def test_reference_data_includes_common_aerospace_metals():
    assert "6061-T6" in REFERENCE_DATA
    assert "Ti-6Al-4V" in REFERENCE_DATA


def test_reference_data_includes_composite_failure_theories():
    assert "Tsai-Hill" in REFERENCE_DATA
    assert "Tsai-Wu" in REFERENCE_DATA


def test_reference_data_includes_gdt_symbols():
    assert "flatness" in REFERENCE_DATA.lower()
    assert "perpendicularity" in REFERENCE_DATA.lower()


def test_reference_data_includes_verification_caveat():
    assert "verify" in REFERENCE_DATA.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reference_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_data'`

- [ ] **Step 3: Write reference_data.py**

`reference_data.py`:
```python
REFERENCE_DATA = """\
REFERENCE DATA (curated, typical/handbook values -- always verify against the actual \
material certification, fastener specification, or drawing callout before use in a \
flight design; these are starting points, not certified values).

## Common Aerospace Metals (room temperature, typical values)

| Material                | Density (g/cm3) | E (GPa) | Yield (MPa) | UTS (MPa) | CTE (um/m-C) |
|-------------------------|------------------|---------|-------------|-----------|--------------|
| Aluminum 6061-T6        | 2.70             | 68.9    | 276         | 310       | 23.6         |
| Aluminum 7075-T6        | 2.81             | 71.7    | 503         | 572       | 23.4         |
| Titanium Ti-6Al-4V      | 4.43             | 113.8   | 880         | 950       | 8.6          |
| Stainless 17-4PH (H900) | 7.75             | 196     | 1170        | 1310      | 10.8         |

## Carbon Fiber / Epoxy, Unidirectional (typical aerospace-grade prepreg)

- Longitudinal modulus E1: 150-165 GPa
- Transverse modulus E2: 8-10 GPa
- In-plane shear modulus G12: 4-5 GPa
- Major Poisson's ratio v12: ~0.30
- Longitudinal tensile strength (0 deg fiber direction): 2000-2700 MPa
- Longitudinal CTE: -0.5 to 0 um/m-C (near-zero to slightly negative -- useful for \
dimensionally stable structures)

## Composite Failure Theories

- Maximum Stress: failure when any stress component exceeds its allowable in that \
direction; no interaction between stress components.
- Maximum Strain: same approach as Maximum Stress, applied to strain components.
- Tsai-Hill: single interactive failure index combining all in-plane stress components; \
more realistic than Max Stress/Strain under combined loading, but does not distinguish \
tension from compression allowables.
- Tsai-Wu: general quadratic interactive criterion; distinguishes tension vs. compression \
allowables; the most commonly used interactive criterion in practice.

## Standard Fastener Torque (typical dry/unlubricated, generic reference class -- verify \
against the actual fastener spec, plating, and lubrication before applying)

| Size    | Torque (in-lb) | Torque (Nm) |
|---------|----------------|-------------|
| #4-40   | 4-5            | 0.5-0.6     |
| #6-32   | 9-10           | 1.0-1.1     |
| #8-32   | 20             | 2.3         |
| 1/4-20  | 90-100         | 10.2-11.3   |
| 5/16-18 | 200            | 22.6        |
| M3      | --             | 1.0-1.3     |
| M4      | --             | 2.5-3.0     |
| M5      | --             | 5.0-6.0     |
| M6      | --             | 8.0-10.0    |

## GD&T Symbols (ASME Y14.5)

- Form: Straightness, Flatness, Circularity, Cylindricity
- Profile: Profile of a Line, Profile of a Surface
- Orientation: Angularity, Perpendicularity, Parallelism
- Location: Position, Concentricity, Symmetry
- Runout: Circular Runout, Total Runout
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reference_data.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add reference_data.py tests/test_reference_data.py
git commit -m "Add curated mechanical engineering reference data"
```

---

### Task 3: System prompt

**Files:**
- Create: `system_prompt.py`
- Test: `tests/test_system_prompt.py`

**Interfaces:**
- Produces: `system_prompt.SYSTEM_PROMPT: str` — consumed by `llm.py` (Task 4).

- [ ] **Step 1: Write the failing test**

`tests/test_system_prompt.py`:
```python
from system_prompt import SYSTEM_PROMPT


def test_forbids_register_simplification():
    assert "simplif" in SYSTEM_PROMPT.lower()


def test_requires_shown_work():
    assert "show" in SYSTEM_PROMPT.lower()


def test_names_full_subject_breadth():
    lowered = SYSTEM_PROMPT.lower()
    for topic in [
        "statics", "dynamics", "mechanics of materials", "thermodynamics",
        "heat transfer", "composite", "vibrations", "materials science",
        "gd&t", "fasteners", "manufacturing",
    ]:
        assert topic in lowered, f"missing topic: {topic}"


def test_treats_masters_level_as_floor_not_ceiling():
    lowered = SYSTEM_PROMPT.lower()
    assert "floor" in lowered
    assert "master" in lowered


def test_is_satellite_aware_not_satellite_only():
    lowered = SYSTEM_PROMPT.lower()
    assert "satellite" in lowered or "spacecraft" in lowered
    assert "not every question" in lowered or "equally in scope" in lowered


def test_includes_verify_flag_convention_and_safety_guardrail():
    assert "VERIFY:" in SYSTEM_PROMPT
    assert "certified" in SYSTEM_PROMPT.lower()


def test_instructs_preferring_reference_data():
    assert "reference" in SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_system_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'system_prompt'`

- [ ] **Step 3: Write system_prompt.py**

`system_prompt.py`:
```python
SYSTEM_PROMPT = """\
You are a mechanical engineering assistant for engineers at an aerospace company that has \
no mechanical engineer on staff. The people asking you questions may be electrical \
engineers, software engineers, systems engineers, or technicians -- not mechanical \
specialists themselves -- but the gap you are filling is real engineering judgment, not \
simplified explanations.

CORE RULE -- DO NOT SIMPLIFY BASED ON HOW THE QUESTION IS PHRASED.
A casually worded question ("why does this bracket keep cracking?") is not a request for \
a casual answer. Always respond with full technical rigor: real equations, correct \
terminology, actual numbers. Never default to a simplified, hand-wavy explanation because \
the asker sounds non-technical. If the person wants a simpler explanation, they will ask \
for one -- do not simplify pre-emptively.

SHOW YOUR WORK.
Give derivations and reasoning, not just conclusions. State the governing equations you \
are using, the assumptions you are making, and the numbers you plug in. A bare final \
answer is not useful to someone who has to defend the decision later.

SUBJECT BREADTH.
You are expected to be fluent across the full range of mechanical engineering, at least to \
the depth of an engineer with a master's degree or several years of post-undergraduate \
aerospace experience -- treat that as a floor, not a target. Cover statics and dynamics, \
mechanics of materials and stress analysis, thermodynamics and heat transfer, composite \
materials and laminate theory, vibrations, materials science, GD&T and tolerancing, \
fasteners, and manufacturing processes / design for manufacturability (DFM). Do not let \
depth drop in any of these areas relative to the others.

SATELLITE-AWARE, NOT SATELLITE-ONLY.
The hardware in question is often satellite/spacecraft hardware. Bring up launch vibration \
and quasi-static loads, thermal vacuum behavior, outgassing-safe material selection, and \
similar spaceflight-specific concerns when they are relevant to the question -- but not \
every question is about spacecraft, and general mechanical engineering questions are \
equally in scope.

REFERENCE DATA.
You have a curated reference sheet of material properties, fastener torque values, GD&T \
symbols, and composite data appended below this prompt. Prefer those curated reference \
values over your own recalled numbers whenever they overlap -- they have been checked \
specifically for this purpose.

SAFETY / SIGN-OFF GUARDRAIL.
This company has no mechanical engineer on staff, so your answer may be the only technical \
review a decision gets before hardware is built. For anything flight-critical, \
load-bearing, or otherwise safety-relevant, say so plainly and flag it. Prefix that flag \
with the literal text "VERIFY:" on its own line, followed by a one-sentence explanation of \
what needs to be checked and by whom, e.g.:

VERIFY: this bracket's margin of safety should be confirmed by structural analysis or test \
before flight -- this estimate is not a substitute for a certified stress analysis.

Use this flag whenever a wrong answer would have real consequences, not for routine or \
low-stakes questions.
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_system_prompt.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add system_prompt.py tests/test_system_prompt.py
git commit -m "Add mechanical engineering system prompt"
```

---

### Task 4: Gemini wrapper (llm.py)

**Files:**
- Create: `llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `config.GEMINI_API_KEY`, `config.GEMINI_MODEL` (Task 1); `system_prompt.SYSTEM_PROMPT` (Task 3); `reference_data.REFERENCE_DATA` (Task 2).
- Produces: `llm.LLMError(Exception)`, `llm.build_full_system_instruction() -> str`, `llm.get_response(history: list[dict]) -> str` where each `history` item is `{"role": "user" | "model", "content": str}`. Consumed by `main.py` (Task 5).

- [ ] **Step 1: Write the failing tests**

`tests/test_llm.py`:
```python
from unittest.mock import patch, MagicMock

import pytest

from llm import get_response, build_full_system_instruction, LLMError


def test_build_full_system_instruction_includes_persona_and_reference_data():
    instruction = build_full_system_instruction()
    assert "mechanical engineering assistant" in instruction.lower()
    assert "6061-T6" in instruction


@patch("llm.genai.GenerativeModel")
def test_get_response_passes_system_instruction_and_prior_history(mock_model_cls):
    mock_chat = MagicMock()
    mock_chat.send_message.return_value.text = "Use Al 6061-T6."
    mock_model_cls.return_value.start_chat.return_value = mock_chat

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    reply = get_response(history)

    assert reply == "Use Al 6061-T6."

    _, kwargs = mock_model_cls.call_args
    assert "mechanical engineering assistant" in kwargs["system_instruction"].lower()

    start_chat_kwargs = mock_model_cls.return_value.start_chat.call_args.kwargs
    passed_history = start_chat_kwargs["history"]
    assert passed_history == [
        {"role": "user", "parts": ["What material for a bracket?"]},
        {"role": "model", "parts": ["Tell me more about the loads."]},
    ]
    mock_chat.send_message.assert_called_once_with("It's a mounting bracket, light load.")


@patch("llm.genai.GenerativeModel")
def test_get_response_raises_llmerror_on_api_failure(mock_model_cls):
    mock_model_cls.return_value.start_chat.side_effect = Exception("network error")

    with pytest.raises(LLMError):
        get_response([{"role": "user", "content": "hi"}])


def test_get_response_raises_llmerror_on_empty_history():
    with pytest.raises(LLMError):
        get_response([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm'`

- [ ] **Step 3: Write llm.py**

`llm.py`:
```python
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from reference_data import REFERENCE_DATA
from system_prompt import SYSTEM_PROMPT


class LLMError(Exception):
    """Raised when the Gemini API call fails or the request is invalid."""


def build_full_system_instruction() -> str:
    return f"{SYSTEM_PROMPT}\n\n{REFERENCE_DATA}"


def get_response(history: list[dict]) -> str:
    if not history:
        raise LLMError("Cannot get a response for an empty conversation.")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=build_full_system_instruction(),
    )

    prior_turns = [
        {"role": turn["role"], "parts": [turn["content"]]}
        for turn in history[:-1]
    ]
    latest_message = history[-1]["content"]

    try:
        chat = model.start_chat(history=prior_turns)
        response = chat.send_message(latest_message)
    except Exception as exc:
        raise LLMError(f"Gemini API call failed: {exc}") from exc

    return response.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add llm.py tests/test_llm.py
git commit -m "Add Gemini wrapper for the ME assistant"
```

---

### Task 5: FastAPI backend

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `llm.get_response(history: list[dict]) -> str`, `llm.LLMError` (Task 4).
- Produces: `POST /chat` accepting `{"history": [{"role": str, "content": str}, ...]}`, returning `{"reply": str}` on success (200) or `{"error": str}` on failure (502). `GET /` serves `static/index.html`. Consumed by the frontend (Task 6).

- [ ] **Step 1: Write the failing tests**

`tests/test_main.py`:
```python
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from llm import LLMError

client = TestClient(app)


@patch("main.get_response")
def test_chat_endpoint_returns_reply(mock_get_response):
    mock_get_response.return_value = "Use a fillet radius of at least 0.5 mm."

    response = client.post(
        "/chat",
        json={"history": [{"role": "user", "content": "Fillet radius for a stress concentration?"}]},
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "Use a fillet radius of at least 0.5 mm."}
    mock_get_response.assert_called_once_with(
        [{"role": "user", "content": "Fillet radius for a stress concentration?"}]
    )


@patch("main.get_response")
def test_chat_endpoint_returns_502_on_llm_failure(mock_get_response):
    mock_get_response.side_effect = LLMError("Gemini API call failed: network error")

    response = client.post("/chat", json={"history": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 502
    assert response.json() == {"error": "Gemini API call failed: network error"}


def test_root_serves_frontend():
    response = client.get("/")

    assert response.status_code == 200
    assert "ME-ASSIST" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'` (and later, once `main.py` exists but before Task 6, the static test will fail with a missing-file error -- that's expected until Task 6 is done)

- [ ] **Step 3: Write main.py**

`main.py`:
```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm import LLMError, get_response

app = FastAPI()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: list[Message]


@app.post("/chat")
def chat(request: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]
    try:
        reply = get_response(history)
    except LLMError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    return {"reply": reply}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: The two `/chat` tests PASS. `test_root_serves_frontend` FAILS until Task 6 creates `static/index.html` — that is expected at this point in the plan.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "Add FastAPI backend with /chat endpoint"
```

---

### Task 6: Frontend chat UI

**Files:**
- Create: `static/index.html`

**Interfaces:**
- Consumes: `POST /chat` (Task 5), request body `{"history": [{"role": "user"|"model", "content": str}]}`, response `{"reply": str}` or `{"error": str}`.

**Design (via the `frontend-design` skill):** an "engineering log sheet" rather than a chat-bubble UI — a title-block header (`SHEET`/`SCALE`/`REV` fields, like a real drawing sheet), each exchange rendered as a numbered log entry (`001 QUERY` / `001 RESPONSE`, mirroring real lab-notebook/revision numbering) separated by hairline rules, `Space Grotesk` for the header/labels, `Source Serif 4` for the long-form technical prose in responses, `IBM Plex Mono` for data/specs/index numbers. Deep blueprint-navy background (`#14242E`) with off-white "linework" text (`#EDEAE0`), a cyan "chalk line" accent for the user's own input (`#4FA8C9`), and an amber safety-tag accent (`#E8A33D`) reserved specifically for rendering the system prompt's `VERIFY:` flags — the one color with real semantic meaning, not decoration. A thin dashed line animates (like a pen drawing) while waiting on a response; disabled under `prefers-reduced-motion`.

- [ ] **Step 1: Write static/index.html**

`static/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ME-ASSIST</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #14242E;
    --surface: #1C3444;
    --rule: #33505F;
    --ink: #EDEAE0;
    --ink-muted: #8FA3AD;
    --accent-flag: #E8A33D;
    --accent-user: #4FA8C9;
    --error: #D9694F;
    --font-display: 'Space Grotesk', sans-serif;
    --font-body: 'Source Serif 4', serif;
    --font-mono: 'IBM Plex Mono', monospace;
  }

  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 17px;
    line-height: 1.6;
  }

  .sheet {
    display: flex;
    flex-direction: column;
    height: 100vh;
    max-width: 760px;
    margin: 0 auto;
    border-left: 1px solid var(--rule);
    border-right: 1px solid var(--rule);
  }

  .title-block {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 14px 20px;
    border-bottom: 1px solid var(--rule);
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.08em;
    color: var(--ink-muted);
    flex-wrap: wrap;
  }
  .title-block__name {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.02em;
    color: var(--ink);
    margin-right: auto;
  }

  .log {
    flex: 1;
    overflow-y: auto;
    padding: 24px 20px 8px;
  }
  .log__empty {
    color: var(--ink-muted);
    font-size: 15px;
    max-width: 46ch;
    padding-top: 40px;
  }

  .entry { margin-bottom: 28px; }
  .entry__meta {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding-bottom: 6px;
    margin-bottom: 10px;
    border-bottom: 1px solid var(--rule);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--ink-muted);
  }
  .entry--query .entry__label { color: var(--accent-user); }
  .entry--response .entry__label { color: var(--ink); }
  .entry--error .entry__label { color: var(--error); }
  .entry--error { border-left: 2px solid var(--error); padding-left: 14px; }

  .entry__body p { margin: 0 0 12px; }
  .entry__body p:last-child { margin-bottom: 0; }
  .entry__body code {
    font-family: var(--font-mono);
    font-size: 0.9em;
    background: var(--surface);
    padding: 1px 5px;
    border-radius: 3px;
  }
  .entry__body ul { margin: 0 0 12px; padding-left: 20px; }
  .entry__body .flag {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    background: rgba(232, 163, 61, 0.12);
    border-left: 2px solid var(--accent-flag);
    color: var(--accent-flag);
    padding: 8px 12px;
    font-family: var(--font-mono);
    font-size: 13px;
    margin: 12px 0;
    border-radius: 0 3px 3px 0;
  }

  .pending { display: flex; align-items: center; gap: 10px; padding: 4px 0 20px; }
  .pending__line {
    display: block;
    width: 60px;
    height: 2px;
    background: repeating-linear-gradient(90deg, var(--accent-user) 0 6px, transparent 6px 10px);
    animation: draw 1s linear infinite;
  }
  @keyframes draw { to { background-position: 16px 0; } }

  .sr-only {
    position: absolute;
    width: 1px; height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }

  .input-bar {
    display: flex;
    gap: 10px;
    align-items: flex-end;
    padding: 16px 20px;
    border-top: 1px solid var(--rule);
    background: var(--bg);
  }
  .input-bar__field {
    flex: 1;
    resize: none;
    max-height: 200px;
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--rule);
    border-radius: 4px;
    padding: 10px 12px;
    font-family: var(--font-body);
    font-size: 15px;
    line-height: 1.4;
  }
  .input-bar__field:focus-visible {
    outline: 2px solid var(--accent-user);
    outline-offset: 1px;
  }
  .input-bar__send {
    background: var(--accent-user);
    color: var(--bg);
    border: none;
    border-radius: 4px;
    width: 40px;
    height: 40px;
    font-size: 16px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .input-bar__send:hover { filter: brightness(1.1); }
  .input-bar__send:focus-visible {
    outline: 2px solid var(--ink);
    outline-offset: 2px;
  }

  @media (prefers-reduced-motion: reduce) {
    .pending__line { animation: none; }
  }

  @media (max-width: 600px) {
    .sheet { border-left: none; border-right: none; }
    .title-block { padding: 12px 16px; gap: 14px; font-size: 11px; }
    .log { padding: 20px 16px 8px; }
    .input-bar { padding: 12px 16px; }
    body { font-size: 16px; }
  }
</style>
</head>
<body>
  <div class="sheet">
    <header class="title-block">
      <span class="title-block__name">ME-ASSIST</span>
      <span class="title-block__field">SHEET <span id="sheet-num">001</span></span>
      <span class="title-block__field">SCALE N/A</span>
      <span class="title-block__field">REV &mdash;</span>
    </header>

    <main class="log" id="log" aria-live="polite">
      <div class="log__empty" id="empty-state">
        <p>No entries yet. Ask a mechanical engineering question below &mdash; statics, materials, thermal, composites, tolerancing, whatever you've got.</p>
      </div>
    </main>

    <form class="input-bar" id="input-form">
      <textarea id="input" class="input-bar__field" placeholder="Ask a mechanical engineering question&hellip;" rows="1" required></textarea>
      <button type="submit" class="input-bar__send" aria-label="Send">&#10148;</button>
    </form>
  </div>

<script>
  const log = document.getElementById('log');
  const emptyState = document.getElementById('empty-state');
  const form = document.getElementById('input-form');
  const input = document.getElementById('input');
  const sheetNum = document.getElementById('sheet-num');

  let history = [];
  let entryIndex = 0;

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

  function appendEntry(role, index, label, bodyHTML, extraClass) {
    if (emptyState && emptyState.parentNode) emptyState.remove();
    const article = document.createElement('article');
    article.className = `entry entry--${role}${extraClass ? ' ' + extraClass : ''}`;
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

  function showPending() {
    const div = document.createElement('div');
    div.className = 'pending';
    div.id = 'pending-indicator';
    div.innerHTML = '<span class="pending__line" aria-hidden="true"></span><span class="sr-only">Computing response&hellip;</span>';
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function removePending() {
    const el = document.getElementById('pending-indicator');
    if (el) el.remove();
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    entryIndex += 1;
    sheetNum.textContent = pad(entryIndex);
    appendEntry('query', entryIndex, 'QUERY', formatBody(text));
    history.push({ role: 'user', content: text });
    input.value = '';
    input.style.height = 'auto';
    showPending();

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history }),
      });
      removePending();

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        appendEntry('error', entryIndex, 'ERROR', formatBody(err.error || 'Something went wrong. Try again.'));
        return;
      }

      const data = await res.json();
      appendEntry('response', entryIndex, 'RESPONSE', formatBody(data.reply));
      history.push({ role: 'model', content: data.reply });
    } catch (err) {
      removePending();
      appendEntry('error', entryIndex, 'ERROR', formatBody('Connection failed. Check your network and try again.'));
    }
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

- [ ] **Step 2: Run the full test suite to verify Task 5's static-serving test now passes**

Run: `pytest tests/ -v`
Expected: All tests PASS, including `test_root_serves_frontend`.

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "Add engineering-log-styled chat UI"
```

---

### Task 7: README and manual end-to-end verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

`README.md`:
```markdown
# ME Assistant

A chat assistant for mechanical engineering questions, for engineers at a
company with no ME on staff. Answers come from Gemini with a system prompt
tuned for full technical rigor, not simplified explanations, plus a curated
reference sheet (materials, fasteners, GD&T, composites) to reduce
hallucination on specific numbers.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key-here"
# optional: export GEMINI_MODEL="gemini-2.5-pro" (this is the default)
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000` in a browser.

## Test

```bash
pytest tests/ -v
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Add README with setup and run instructions"
```

- [ ] **Step 3: Manual end-to-end verification**

With a real `GEMINI_API_KEY` exported, run `uvicorn main:app --reload --port 8000` and open `http://127.0.0.1:8000`. Confirm:
- The title block reads `ME-ASSIST`, `SHEET 001`, `SCALE N/A`, `REV —` before any messages are sent.
- Sending "What material would you use for a lightweight satellite mounting bracket, and why?" produces a `001 QUERY` / `001 RESPONSE` pair, `SHEET` updates to `001`, and the response shows real reasoning (not a one-line answer) with correct terminology.
- Asking a flight-critical structural question (e.g. "what's the margin of safety on a 5mm 6061-T6 bracket under a 200N load?") produces a response containing an amber-highlighted `VERIFY:` flag box, distinct from the surrounding text.
- Temporarily setting `GEMINI_API_KEY` to an invalid value and restarting the server, then sending a message, produces a visible `ERROR`-labeled entry with a red left border rather than a silent failure or crash.
- Resizing the browser to a mobile width (< 600px) keeps the input bar usable and the log readable without horizontal scrolling.
- Tabbing to the input field and send button shows a visible focus outline.
