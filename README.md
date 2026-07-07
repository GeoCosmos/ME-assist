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

## Run

```bash
uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000` in a browser.

## Test

```bash
pytest tests/ -v
```
