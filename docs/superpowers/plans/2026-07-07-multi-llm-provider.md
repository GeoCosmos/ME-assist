# Multi-LLM Provider Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the ME-assistant app switch between Gemini, Claude, and OpenAI via config instead of being hard-wired to Gemini.

**Architecture:** `llm.py` becomes a package (`llm/`) with a `base.py` (shared `LLMError` + `build_full_system_instruction`), one adapter module per provider (`gemini.py`, `anthropic.py`, `openai.py`, each exposing a class with `get_response_stream(history)`), and `__init__.py` holding a registry-based factory that dispatches to the adapter named by `config.LLM_PROVIDER`.

**Tech Stack:** Python, FastAPI, `google-genai`, `anthropic`, `openai`, pytest, `unittest.mock`.

## Global Constraints

- `LLM_PROVIDER` env var default: `"gemini"` (existing deployments need zero env changes).
- `ANTHROPIC_MODEL` default: `"claude-sonnet-5"`. `OPENAI_MODEL` default: `"gpt-5"`.
- No runtime/UI provider switching — provider is fixed for the process lifetime.
- No local/Ollama provider, no cross-provider fallback/retry.
- Every provider adapter wraps its own SDK's exceptions into the shared `LLMError`, matching the existing Gemini pattern (`except Exception as exc: raise LLMError(f"... API call failed: {exc}") from exc`).
- `/model-info` returns `{"provider": ..., "model": ...}`.
- `main.py`'s public imports (`from llm import LLMError, get_response_stream`) must keep working unchanged.

---

### Task 1: Add multi-provider config fields

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.LLM_PROVIDER: str`, `config.ANTHROPIC_API_KEY: str`, `config.ANTHROPIC_MODEL: str`, `config.OPENAI_API_KEY: str`, `config.OPENAI_MODEL: str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
def test_default_provider_when_env_not_set(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "gemini"


def test_provider_reads_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "anthropic"


def test_default_anthropic_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    import config
    importlib.reload(config)
    assert config.ANTHROPIC_MODEL == "claude-sonnet-5"


def test_anthropic_model_reads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-custom")
    import config
    importlib.reload(config)
    assert config.ANTHROPIC_MODEL == "claude-custom"


def test_anthropic_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-456")
    import config
    importlib.reload(config)
    assert config.ANTHROPIC_API_KEY == "test-key-456"


def test_default_openai_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    import config
    importlib.reload(config)
    assert config.OPENAI_MODEL == "gpt-5"


def test_openai_model_reads_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-custom")
    import config
    importlib.reload(config)
    assert config.OPENAI_MODEL == "gpt-custom"


def test_openai_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-789")
    import config
    importlib.reload(config)
    assert config.OPENAI_API_KEY == "test-key-789"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: the 8 new tests FAIL with `AttributeError: module 'config' has no attribute 'LLM_PROVIDER'` (or `ANTHROPIC_MODEL`/etc).

- [ ] **Step 3: Implement the config fields**

Replace the full contents of `config.py` with:

```python
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "Add LLM_PROVIDER and per-provider config fields"
```

---

### Task 2: Restructure `llm.py` into a `llm/` package (Gemini only, behavior-preserving)

**Files:**
- Create: `llm/base.py`
- Create: `llm/gemini.py`
- Create: `llm/__init__.py`
- Delete: `llm.py`
- Create: `tests/llm/test_gemini.py`
- Modify: `tests/test_llm.py` (full rewrite)

**Interfaces:**
- Consumes: `config.LLM_PROVIDER`, `config.GEMINI_API_KEY`, `config.GEMINI_MODEL` (Task 1).
- Produces: `llm.LLMError`, `llm.build_full_system_instruction() -> str`, `llm.get_response_stream(history: list[dict]) -> Iterator[str]`, `llm.current_model() -> str`, `llm._PROVIDERS: dict[str, type]`, `llm._MODELS: dict[str, str]`, `llm.base.LLMError`, `llm.base.build_full_system_instruction`, `llm.gemini.GeminiProvider` (class with `get_response_stream(self, history: list[dict]) -> Iterator[str]`).

- [ ] **Step 1: Write the failing tests**

```bash
mkdir -p tests/llm
```

Create `tests/llm/test_gemini.py`:

```python
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
```

Replace the full contents of `tests/test_llm.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm.py tests/llm/test_gemini.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm.base'` (or `'llm.gemini'`) since `llm.py` is still a flat module, not a package.

- [ ] **Step 3: Implement the package**

Create `llm/base.py`:

```python
from collections.abc import Iterator
from typing import Protocol

from reference_data import REFERENCE_DATA
from system_prompt import SYSTEM_PROMPT


class LLMError(Exception):
    """Raised when an LLM provider call fails or the request is invalid."""


class Provider(Protocol):
    def get_response_stream(self, history: list[dict]) -> Iterator[str]: ...


def build_full_system_instruction() -> str:
    return f"{SYSTEM_PROMPT}\n\n{REFERENCE_DATA}"
```

Create `llm/gemini.py`:

```python
from collections.abc import Iterator

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from llm.base import LLMError, build_full_system_instruction


class GeminiProvider:
    def get_response_stream(self, history: list[dict]) -> Iterator[str]:
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

Create `llm/__init__.py`:

```python
from collections.abc import Iterator

from config import GEMINI_MODEL, LLM_PROVIDER
from llm.base import LLMError, build_full_system_instruction
from llm.gemini import GeminiProvider

_PROVIDERS = {
    "gemini": GeminiProvider,
}

_MODELS = {
    "gemini": GEMINI_MODEL,
}


def current_model() -> str:
    try:
        return _MODELS[LLM_PROVIDER]
    except KeyError:
        raise LLMError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}") from None


def get_response_stream(history: list[dict]) -> Iterator[str]:
    if not history:
        raise LLMError("Cannot get a response for an empty conversation.")

    try:
        provider_cls = _PROVIDERS[LLM_PROVIDER]
    except KeyError:
        raise LLMError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}") from None

    yield from provider_cls().get_response_stream(history)
```

Delete the old flat module:

```bash
rm llm.py
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm.py tests/llm/test_gemini.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `pytest tests/ -v`
Expected: all PASS (`tests/test_main.py` still imports `from llm import LLMError, get_response_stream` and `from config import GEMINI_MODEL`, both still valid).

- [ ] **Step 6: Commit**

```bash
git add llm.py llm/ tests/test_llm.py tests/llm/
git commit -m "Restructure llm.py into a provider-adapter package"
```

---

### Task 3: Add Anthropic (Claude) provider

**Files:**
- Modify: `requirements.txt`
- Create: `llm/anthropic.py`
- Modify: `llm/__init__.py`
- Create: `tests/llm/test_anthropic.py`
- Modify: `tests/test_llm.py`

**Interfaces:**
- Consumes: `config.ANTHROPIC_API_KEY`, `config.ANTHROPIC_MODEL` (Task 1); `llm.base.LLMError`, `llm.base.build_full_system_instruction` (Task 2).
- Produces: `llm.anthropic.AnthropicProvider` (class with `get_response_stream(self, history: list[dict]) -> Iterator[str]`); registers `"anthropic"` in `llm._PROVIDERS` and `llm._MODELS`.

- [ ] **Step 1: Add the dependency**

Append `anthropic` to `requirements.txt` (new file contents):

```
fastapi
uvicorn
google-genai
anthropic
pydantic
pytest
httpx
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/llm/test_anthropic.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/llm/test_anthropic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm.anthropic'`.

- [ ] **Step 4: Implement the provider**

Create `llm/anthropic.py`:

```python
from collections.abc import Iterator

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from llm.base import LLMError, build_full_system_instruction

_ROLE_MAP = {"user": "user", "model": "assistant"}


class AnthropicProvider:
    def get_response_stream(self, history: list[dict]) -> Iterator[str]:
        messages = [
            {"role": _ROLE_MAP[turn["role"]], "content": turn["content"]}
            for turn in history
        ]

        try:
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            with client.messages.stream(
                model=ANTHROPIC_MODEL,
                max_tokens=8192,
                system=build_full_system_instruction(),
                messages=messages,
            ) as stream:
                yield from stream.text_stream
        except Exception as exc:
            raise LLMError(f"Anthropic API call failed: {exc}") from exc
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/llm/test_anthropic.py -v`
Expected: PASS.

- [ ] **Step 6: Register the provider and add a registry test**

Modify `llm/__init__.py` — update the imports and both registry dicts:

```python
from collections.abc import Iterator

from config import ANTHROPIC_MODEL, GEMINI_MODEL, LLM_PROVIDER
from llm.anthropic import AnthropicProvider
from llm.base import LLMError, build_full_system_instruction
from llm.gemini import GeminiProvider

_PROVIDERS = {
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
}

_MODELS = {
    "gemini": GEMINI_MODEL,
    "anthropic": ANTHROPIC_MODEL,
}
```

(The rest of `llm/__init__.py` — `current_model()` and `get_response_stream()` — is unchanged from Task 2.)

Append to `tests/test_llm.py`:

```python
def test_anthropic_provider_is_registered():
    import llm
    from config import ANTHROPIC_MODEL
    from llm.anthropic import AnthropicProvider

    assert llm._PROVIDERS["anthropic"] is AnthropicProvider
    assert llm._MODELS["anthropic"] == ANTHROPIC_MODEL
```

- [ ] **Step 7: Run the full suite**

Run: `pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt llm/anthropic.py llm/__init__.py tests/llm/test_anthropic.py tests/test_llm.py
git commit -m "Add Anthropic (Claude) provider"
```

---

### Task 4: Add OpenAI provider

**Files:**
- Modify: `requirements.txt`
- Create: `llm/openai.py`
- Modify: `llm/__init__.py`
- Create: `tests/llm/test_openai.py`
- Modify: `tests/test_llm.py`

**Interfaces:**
- Consumes: `config.OPENAI_API_KEY`, `config.OPENAI_MODEL` (Task 1); `llm.base.LLMError`, `llm.base.build_full_system_instruction` (Task 2).
- Produces: `llm.openai.OpenAIProvider` (class with `get_response_stream(self, history: list[dict]) -> Iterator[str]`); registers `"openai"` in `llm._PROVIDERS` and `llm._MODELS`.

- [ ] **Step 1: Add the dependency**

Append `openai` to `requirements.txt` (new file contents):

```
fastapi
uvicorn
google-genai
anthropic
openai
pydantic
pytest
httpx
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/llm/test_openai.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from llm.base import LLMError
from llm.openai import OpenAIProvider


def _chunk(text):
    return MagicMock(choices=[MagicMock(delta=MagicMock(content=text))])


@patch("llm.openai.OpenAI")
def test_get_response_stream_yields_deltas_and_passes_system_instruction_and_history(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.return_value = iter(
        [_chunk("Use "), _chunk("Al 6061-T6.")]
    )

    history = [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "model", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]
    deltas = list(OpenAIProvider().get_response_stream(history))

    assert deltas == ["Use ", "Al 6061-T6."]

    _, kwargs = mock_openai_cls.return_value.chat.completions.create.call_args
    assert kwargs["messages"][0]["role"] == "system"
    assert "mechanical engineering assistant" in kwargs["messages"][0]["content"].lower()
    assert kwargs["messages"][1:] == [
        {"role": "user", "content": "What material for a bracket?"},
        {"role": "assistant", "content": "Tell me more about the loads."},
        {"role": "user", "content": "It's a mounting bracket, light load."},
    ]


@patch("llm.openai.OpenAI")
def test_get_response_stream_raises_llmerror_on_api_failure(mock_openai_cls):
    mock_openai_cls.return_value.chat.completions.create.side_effect = Exception("network error")

    with pytest.raises(LLMError):
        list(OpenAIProvider().get_response_stream([{"role": "user", "content": "hi"}]))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/llm/test_openai.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm.openai'`.

- [ ] **Step 4: Implement the provider**

Create `llm/openai.py`:

```python
from collections.abc import Iterator

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from llm.base import LLMError, build_full_system_instruction

_ROLE_MAP = {"user": "user", "model": "assistant"}


class OpenAIProvider:
    def get_response_stream(self, history: list[dict]) -> Iterator[str]:
        messages = [{"role": "system", "content": build_full_system_instruction()}]
        messages += [
            {"role": _ROLE_MAP[turn["role"]], "content": turn["content"]}
            for turn in history
        ]

        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            stream = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMError(f"OpenAI API call failed: {exc}") from exc
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/llm/test_openai.py -v`
Expected: PASS.

- [ ] **Step 6: Register the provider and add a registry test**

Modify `llm/__init__.py` — update the imports and both registry dicts:

```python
from collections.abc import Iterator

from config import ANTHROPIC_MODEL, GEMINI_MODEL, LLM_PROVIDER, OPENAI_MODEL
from llm.anthropic import AnthropicProvider
from llm.base import LLMError, build_full_system_instruction
from llm.gemini import GeminiProvider
from llm.openai import OpenAIProvider

_PROVIDERS = {
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}

_MODELS = {
    "gemini": GEMINI_MODEL,
    "anthropic": ANTHROPIC_MODEL,
    "openai": OPENAI_MODEL,
}
```

(The rest of `llm/__init__.py` is unchanged from Task 3.)

Append to `tests/test_llm.py`:

```python
def test_openai_provider_is_registered():
    import llm
    from config import OPENAI_MODEL
    from llm.openai import OpenAIProvider

    assert llm._PROVIDERS["openai"] is OpenAIProvider
    assert llm._MODELS["openai"] == OPENAI_MODEL
```

- [ ] **Step 7: Run the full suite**

Run: `pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt llm/openai.py llm/__init__.py tests/llm/test_openai.py tests/test_llm.py
git commit -m "Add OpenAI provider"
```

---

### Task 5: Make `/model-info` provider-aware

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `config.LLM_PROVIDER` (Task 1), `llm.current_model()` (Task 2).
- Produces: `GET /model-info` returns `{"provider": str, "model": str}`.

- [ ] **Step 1: Write the failing test**

In `tests/test_main.py`, change the import line:

```python
from config import GEMINI_MODEL, LLM_PROVIDER
```

Replace the `test_model_info_returns_configured_model` test with:

```python
def test_model_info_returns_configured_provider_and_model():
    response = client.get("/model-info")

    assert response.status_code == 200
    assert response.json() == {"provider": LLM_PROVIDER, "model": GEMINI_MODEL}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — the endpoint still returns `{"model": GEMINI_MODEL}` without a `"provider"` key.

- [ ] **Step 3: Implement the endpoint change**

In `main.py`, change:

```python
from config import GEMINI_MODEL
from llm import LLMError, get_response_stream
```

to:

```python
from config import LLM_PROVIDER
from llm import LLMError, current_model, get_response_stream
```

Change the `model_info` function:

```python
@app.get("/model-info")
def model_info():
    return {"provider": LLM_PROVIDER, "model": current_model()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "Make /model-info report the active provider and model"
```

---

### Task 6: Update setup docs

**Files:**
- Modify: `README.md`

**Interfaces:**
- None (docs only).

- [ ] **Step 1: Update the README**

Replace lines 1-25 of `README.md` with:

```markdown
# ME Assistant

A chat assistant for mechanical engineering questions, for engineers at a
company with no ME on staff. Answers come from Gemini, Claude, or OpenAI
(configurable) with a system prompt tuned for full technical rigor, not
simplified explanations, plus a curated reference sheet (materials,
fasteners, GD&T, composites) to reduce hallucination on specific numbers.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Pick which LLM provider to use (defaults to gemini):
export LLM_PROVIDER="gemini"  # or "anthropic" or "openai"

# Gemini (default)
export GEMINI_API_KEY="your-key-here"
# optional: export GEMINI_MODEL="gemini-2.5-flash" (this is the default)

# Anthropic (only needed if LLM_PROVIDER=anthropic)
export ANTHROPIC_API_KEY="your-key-here"
# optional: export ANTHROPIC_MODEL="claude-sonnet-5" (this is the default)

# OpenAI (only needed if LLM_PROVIDER=openai)
export OPENAI_API_KEY="your-key-here"
# optional: export OPENAI_MODEL="gpt-5" (this is the default)
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Document LLM_PROVIDER and per-provider env vars in README"
```
