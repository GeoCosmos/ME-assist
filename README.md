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
# optional: export GEMINI_MODEL="gemini-2.5-flash" (this is the default)
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000` in a browser.

## CLAUDE Skill

If you want to insert the Mechanical Engineering system prompt as a claude skill:
1. Go to the customization tab in the left dashboard of the Claude Browser
2. Click on the Add drop down button
3. Press upload skill and drag/drop the mechanical-engineering.zip file into the ingest area.

## Test

```bash
pytest tests/ -v
```
