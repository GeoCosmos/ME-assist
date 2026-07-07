# Multi-LLM Provider Support

**Status:** Approved by user, ready for implementation.

## Why

The app is hard-wired to Gemini (`llm.py` imports `google.genai` directly). The user
wants to be able to switch between Gemini, Claude, and OpenAI without code changes,
selected via config, so the ME-assistant persona and reference data aren't locked to
one vendor's model.

## Architecture

`llm.py` becomes a package:

```
llm/
  __init__.py   # build_full_system_instruction(), get_response_stream() factory, LLMError
  base.py       # Provider protocol: get_response_stream(history) -> Iterator[str]
  gemini.py     # GeminiProvider (today's genai logic, moved as-is)
  anthropic.py  # AnthropicProvider
  openai.py     # OpenAIProvider
```

`main.py`'s imports (`from llm import LLMError, get_response_stream`) do not change —
the factory in `llm/__init__.py` keeps the same signature the rest of the app already
depends on.

`base.py` defines a `Provider` protocol with one method:
`get_response_stream(history: list[dict]) -> Iterator[str]`. Each provider module
exposes a class implementing it, constructed with no arguments (reads its own API
key/model from `config.py` at call time, matching how `GeminiProvider`'s current logic
reads `GEMINI_API_KEY`/`GEMINI_MODEL`).

## Config (`config.py`)

- `LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")` — default preserves
  today's behavior with zero env changes required for existing deployments.
- `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` (default `"claude-sonnet-5"`).
- `OPENAI_API_KEY` / `OPENAI_MODEL` (default `"gpt-5"`).
- Existing `GEMINI_API_KEY` / `GEMINI_MODEL` unchanged.

## Data flow

`get_response_stream(history)` in `llm/__init__.py`:
1. Raises `LLMError` on empty history (as today).
2. Looks up the provider class for `config.LLM_PROVIDER` in a dict-based registry
   (`{"gemini": GeminiProvider, "anthropic": AnthropicProvider, "openai": OpenAIProvider}`).
3. Raises `LLMError` if `LLM_PROVIDER` doesn't match a known key.
4. Delegates to that provider's `get_response_stream(history)`, yielding its deltas.

Each adapter receives the same `[{"role": "user"/"model", "content": ...}]` history
shape used today and translates it to its own SDK's format internally:
- **Gemini:** unchanged — `role`/`parts` mapping, `system_instruction` on
  `GenerateContentConfig`.
- **Anthropic:** maps `"model"` → `"assistant"`, passes
  `build_full_system_instruction()` as the `system` param, uses
  `client.messages.stream(...)`.
- **OpenAI:** maps `"model"` → `"assistant"`, prepends a `{"role": "system", "content":
  ...}` message, uses `client.chat.completions.create(..., stream=True)`.

`/model-info` changes from `{"model": GEMINI_MODEL}` to `{"provider": LLM_PROVIDER,
"model": <active provider's configured model>}`. `llm/__init__.py` exposes a small
`current_model()` helper (looks up the right `config.*_MODEL` value for
`LLM_PROVIDER`) that `main.py` calls for this endpoint.

## Error handling

- Unknown `LLM_PROVIDER` value raises `LLMError` from the factory, so it surfaces
  through the existing `/chat` SSE error path instead of a 500.
- Each adapter wraps its own SDK's exceptions into `LLMError` exactly like the current
  Gemini code does (`except Exception as exc: raise LLMError(f"... API call failed:
  {exc}") from exc`).
- No new upfront validation for missing API keys — as today, a missing/invalid key
  surfaces naturally when the SDK call fails, and gets wrapped into `LLMError`.

## Testing

- `tests/test_llm.py`: keeps `build_full_system_instruction` tests; adds factory tests
  — correct provider class picked per `LLM_PROVIDER` (monkeypatched), `LLMError` on
  unknown provider value, `LLMError` on empty history.
- `tests/llm/test_gemini.py`, `test_anthropic.py`, `test_openai.py`: one file per
  adapter, each mocking that provider's SDK client, verifying streamed deltas, correct
  history/role translation, system instruction passed through, and `LLMError` on API
  failure — mirroring the existing Gemini test shape.
- `tests/test_config.py`: adds default/env-override tests for `LLM_PROVIDER`,
  `ANTHROPIC_MODEL`, `OPENAI_MODEL` (same pattern as existing `GEMINI_MODEL` tests).
- `tests/test_main.py`: updates `test_model_info_returns_configured_model` for the new
  `{"provider", "model"}` response shape.

## Dependencies / docs

- Add `anthropic` and `openai` to `requirements.txt`.
- Update `README.md` setup section to document `LLM_PROVIDER` and the new per-provider
  env vars, noting the default (`gemini`) requires no changes for existing setups.

## Out of scope

- No runtime/UI provider switching — provider is fixed for the life of the process via
  `LLM_PROVIDER`, matching how `GEMINI_MODEL` already works.
- No local/Ollama provider — only Gemini, Claude, and OpenAI's hosted APIs.
- No fallback/retry across providers if one fails.
