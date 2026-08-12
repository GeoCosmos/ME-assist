# ME Assistant

A chat assistant for mechanical engineering questions, built for a team with no
mechanical engineer on staff. Answers come from Gemini, Groq, OpenAI, or Claude,
with a system prompt tuned for full technical rigor rather than simplified
explanations, plus a curated reference sheet (materials, fasteners, GD&T,
composites, thermal, vibration, manufacturing) to reduce hallucination on
specific numbers.

Two things it does that a plain chat window does not:

- **It uses free API quota first, and never spends money without asking.** When
  the free tiers run out it stops and shows you what the next answer would cost,
  who would answer it, and what you have spent so far. Nothing is billed until
  you click.
- **It has discipline sections.** Selecting one narrows both the system prompt
  and the reference tables to that discipline, so answers get more specific
  while each turn also gets cheaper.

## Getting started

**Windows:** double-click `start.bat`.
**macOS:** double-click `start.command` (first time only, you may need to run
`chmod +x start.command` in Terminal).

The launcher creates the Python environment, installs dependencies, opens the
`.env` file so you can paste in a key, and opens the app in your browser. Later
launches skip straight to running. The console window it opens *is* the server —
close it to stop.

You need Python 3 installed. If the launcher can't find it, get it from
[python.org](https://www.python.org/downloads/) and make sure "Add python.exe to
PATH" is checked on Windows.

## API keys

Click **API KEYS** in the top right of the status bar, or **API KEYS & MODELS**
at the bottom of the left panel. Paste a key, press **TEST** to
confirm it works, then **SAVE**. Keys are written to a local `.env` file next to
the app and never leave the machine. You can also edit `.env` directly.

| Provider | Cost | Get a key |
|---|---|---|
| Groq | Free tier, ~1,000 requests/day | [console.groq.com/keys](https://console.groq.com/keys) |
| Gemini | Free tier, ~20 requests/day | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| OpenAI | Paid, per token | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Anthropic | Paid, per token | [console.anthropic.com](https://console.anthropic.com/settings/keys) |

One key is enough to start, and Groq is the one to get first — its free daily
allowance is roughly 50x Gemini's.

**Free-tier limits shown in the app are editable, and you should check them.**
They are specific to both the model and your account, and published figures
disagree with each other and with reality. Open the settings panel, compare the
REQ/DAY, REQ/MIN and TOKENS/MIN boxes against your provider console, and correct
them. Getting them wrong is not fatal — the app also reacts to real 429s — but
accurate values stop it wasting requests to discover a limit.

## How the provider switch works

Providers are tried in the order set by `LLM_CHAIN` (default
`groq,gemini,openai,anthropic` — Groq leads because Gemini's ~20/day is about
two conversations). Free tiers are used first and silently. A paid
provider is **never** used without an explicit click.

When free quota runs out you get an inline card showing the provider and model
that would answer, the estimated cost of that one answer, what the conversation
has cost so far, and when free quota comes back. You can approve just that
answer, approve for the rest of the conversation, or cancel. Approval is never
remembered across conversations or restarts.

While a conversation is on a paid provider, the status bar badge stays amber and
a running dollar total ticks up beside it, so it is not possible to forget you
are billing.

**Per-minute limits do not cost you money.** Free tiers cap requests per minute
and *tokens* per minute as well as per day. On Groq the token budget (~6,000/min)
is the binding one: it is smaller than one full-reference-sheet prompt, which is
why the reference tables are selected per question rather than sent whole. The app paces its own requests locally against the
published limits, so it steps aside *before* sending rather than burning a 429
to find out. If one free tier is minute-limited it tries the other; if all free
tiers are busy it waits out the window (up to `MAX_FREE_WAIT_SECONDS`, default
25) and tells you it's waiting. Only when free capacity is genuinely minutes
away does it ask about paying — and that card says "rate limited", not "quota
gone", and offers a **RETRY ON FREE** button first.

Two deliberate limits:

- Failover only happens **before the first token reaches the browser**. If a
  provider dies halfway through an answer you get a visible error rather than
  two different models silently stitched into one response.
- Free-tier quota is tracked locally *and* confirmed by the provider's 429
  response, because no API reports remaining quota. The local counter carries a
  safety margin; the 429 is authoritative.

## Discipline sections

The left panel lists eight sections: statics/dynamics, materials, thermal,
composites, vibrations, GD&T, fasteners, and manufacturing. Clicking one **opens
that section as a workspace** — a panel appears above the chat with the
discipline name, what it covers, and its starter questions, and a chip in the
status bar shows which section you are in until you press **EXIT SECTION**.

It does not write anything into the input box. Selecting a section changes how
every following message is answered: it appends a domain brief to the system
prompt — how to structure the analysis, which failure modes to check, which
standards apply — and swaps the reference sheet for just that discipline's
tables. The starter questions inside the panel are optional; clicking one fills
the input, but the section is what changes the answer.

That makes answers both more specific and cheaper. With no section selected the
tables are chosen by keyword from your question (~3,100–3,800 tokens); with a
section selected you get that discipline's full tables and brief. Either way a
turn stays under Groq's 6,000 tokens/minute budget — sending all thirteen
sections (~8,900 tokens) would exceed what one request is allowed to use.

## Choosing which provider answers

Setting a provider's key and model does **not** make it answer — the first
provider in the chain that still has free capacity does. To force one, open the
settings panel and press **USE FIRST** next to it, then SAVE. That reorders
`LLM_CHAIN` so it is tried first.

This is the usual "I changed the model and nothing happened" cause: the model
was changed on a provider that never gets reached.

## Conversations

Transcripts are saved in your browser and survive a refresh, per section. The
paid-provider approval is deliberately **not** saved — a reload never inherits
permission to spend.

**NEW** in the status bar clears the current conversation and starts a fresh
one. Worth using often: the entire history is re-sent with every question, so a
long thread costs several times more per answer than a short one.

## If the UI looks wrong after an update

The app serves its page with `no-store`, so a normal refresh is enough. If you
had a tab open from before an update, hard-refresh once
(**Ctrl+Shift+R**, or **Cmd+Shift+R** on macOS) and restart the server window.
You are on the current UI if the left panel says **DISCIPLINE** at the top and
there is an **API KEYS** button in the status bar.

## Cost tracking

Every turn's token counts and cost are written to a local SQLite ledger
(`usage.db`, gitignored). The **API KEYS** panel shows free quota remaining,
spend today, and spend this month. `GET /usage` returns the same data as JSON.

Rough costs for a 10-turn conversation at August 2026 prices, assuming ~800-token
answers:

| Provider | Cost |
|---|---|
| Groq (free tier) | $0.00 |
| Gemini 2.5 Flash | ~$0.04 |
| GPT-5 | ~$0.15 |
| Claude Sonnet 5 | ~$0.20 |

Cost grows quadratically with conversation length, because the whole history is
re-sent each turn. Starting a fresh conversation for a new question is the
cheapest thing you can do.

## Configuration

Everything is optional and lives in `.env` — see `.env.example` for the full
list with comments.

| Variable | Purpose |
|---|---|
| `LLM_CHAIN` | Provider order, e.g. `gemini,groq,openai,anthropic` |
| `GEMINI_MODEL` etc. | Override the model per provider |
| `GEMINI_FREE_RPD` | Free requests/day — correct this from your console |
| `GEMINI_FREE_RPM` | Free requests/minute |
| `GROQ_FREE_TPM` | Free tokens/minute — usually the binding limit |
| `OPENAI_RPM` etc. | Pace a paid provider too (off by default) |
| `MAX_FREE_WAIT_SECONDS` | How long to wait for free capacity before asking |
| `GEMINI_BILLING_ENABLED` | Treat Gemini as paid (asks before use) |
| `ME_ASSIST_DB` | Move the usage ledger elsewhere |

`LLM_PROVIDER` from earlier versions still works and becomes the head of the
chain.

## Running manually

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python launch.py                  # or: uvicorn main:app --port 8000
```

The server binds to `127.0.0.1` only. Do not expose it on a network — the
settings endpoint can write API keys.

## Troubleshooting

**`sqlite3.OperationalError: unable to open database file`** — the usage ledger
(`usage.db`) is unreadable or its folder is not writable. The app now
quarantines a broken file as `usage.db.broken` and falls back to a writable
location, so this should self-heal. If it persists, delete `usage.db`,
`usage.db-journal` and `usage.db-wal` and restart; you lose only cost history.

**The transcript scrolls under the input box** — fixed; hard-refresh once if you
had the page open from before.

**A model name is rejected** — check the dropdown in settings for valid ids.
Note it is `gemini-3.6-flash`, not `gemini-3-flash`.

## Tests

```bash
pytest tests/ -v                     # backend
node tests/test_ui_markdown.js       # answer rendering (no dependencies)
node tests/test_ui_workspaces.js     # UI behaviour (needs: npm i jsdom)
```

## Claude skill

To use the mechanical engineering system prompt as a Claude skill:

1. Go to the customization tab in the left dashboard of the Claude browser app.
2. Click the **Add** dropdown.
3. Press **Upload skill** and drag `mechanical-engineering.zip` into the ingest area.

## Layout

```
main.py             FastAPI routes and SSE streaming
llm/                provider chain, approval gate, one module per provider
config.py           runtime settings, .env read/write
usage.py            cost ledger, pricing, free-tier quota tracking
ratelimit.py        client-side per-minute pacing and 429 cooldowns
domains.py          discipline sections and their prompt briefs
reference_data.py   sectioned engineering reference tables
system_prompt.py    base persona and rigor rules
launch.py           port selection and browser open
start.bat / .command  double-click launchers
```
