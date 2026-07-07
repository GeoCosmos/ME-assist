# ME Assistant — Design Spec

## Purpose

A chat-style AI assistant that lets Geocosmos engineers (who have no in-house
mechanical engineer) ask mechanical engineering questions and get answers with
real technical rigor — statics, mechanics of materials, thermodynamics/heat
transfer, composites, vibrations, materials science, GD&T/tolerancing,
fasteners, and manufacturing/DFM. Satellite/aerospace context should inform
answers where relevant, but the assistant is not narrowly scoped to spacecraft
— general ME questions are equally in scope.

This is an unconstrained companion to Geo-Assist (Geocosmos's air-gapped,
document-grounded RAG tool): no air-gap requirement, no document grounding,
cloud LLM is fine.

## Non-goals (explicitly out of scope for this version)

- No RAG / document grounding — answers come from the model's own knowledge,
  not retrieval over company documents.
- No conversation persistence — history lives only in the browser tab for the
  session; losing it on refresh or server restart is acceptable.
- No auth, no multi-user accounts — single shared tool, no login.
- No fine-tuning or custom model training.

## Architecture

Two pieces, no database, no vector store:

- A small FastAPI backend with one endpoint (`POST /chat`) that forwards a
  conversation to the Gemini API with a fixed system prompt, and returns the
  reply.
- A single static HTML page (vanilla JS, no build step, no framework) with a
  chat UI: input box, message bubbles, loading state. Visual style follows
  the same simple pattern as Geo-Assist's frontend.

The backend is stateless per request — the frontend sends the full
conversation history with every call; nothing is stored server-side.

## Components

- `main.py` — FastAPI app; `POST /chat` endpoint; serves the static frontend.
- `llm.py` — thin wrapper around the `google-generativeai` SDK. Takes
  (system prompt + reference data + message history) → returns Gemini's
  reply. Mocked in tests the same way Geo-Assist mocks its Ollama wrapper.
- `config.py` — Gemini API key (from env var), model name as a constant.
  Model choice matters more than any prompt wording for response quality —
  use the most capable Gemini model available (e.g. current Pro-tier, not a
  Flash/fast-tier model), configurable via env var so it can be swapped
  without a code change.
- `system_prompt.py` — persona and reasoning-framework instructions (see
  below).
- `reference_data.py` — curated cheat-sheet facts, kept separate from the
  persona/framework prompt so it can be updated independently: common
  aerospace metals (e.g. Al 6061-T6, Ti-6Al-4V) with real properties,
  standard fastener torque values, GD&T symbol reference, common composite
  layups/fiber-matrix properties and failure theories (max stress, Tsai-Will,
  etc.).
- `static/index.html` — the chat UI. Unlike Geo-Assist's utilitarian
  frontend, this one should get real visual design attention (typography,
  color, layout, motion/feedback on send-and-loading states) — built using
  the `frontend-design` skill during implementation rather than a plain
  input-box-and-bubbles default.

## System prompt design

Persona and instructions (not a knowledge injection — Gemini's own training
already contains graduate-level ME content; the prompt's job is to make sure
that depth is actually used rather than defaulted away):

1. **No register simplification based on question phrasing.** The main
   failure mode to guard against: a non-ME employee asks a casually-phrased
   question ("why does this bracket keep cracking?") and the model infers it
   should give a simplified, lay-friendly answer. Instruct it to always
   respond with full technical rigor — real equations, correct terminology,
   actual numbers — regardless of how the question is phrased. The user can
   ask for a simpler explanation if they want one; the default should not be
   simplified.
2. **Show work, not just conclusions.** Ask for derivations/reasoning shown,
   not just final answers — this gets more out of the same underlying model
   capability.
3. **Named subject breadth**, so it doesn't skip depth in domains it might
   otherwise gloss over: statics & dynamics, mechanics of materials/stress
   analysis, thermodynamics & heat transfer, composite materials & laminate
   theory, vibrations, materials science, GD&T/tolerancing, fasteners,
   manufacturing processes/DFM.
4. **Satellite-aware, not satellite-only.** Mention aerospace/satellite
   context (launch vibration/loads, thermal vacuum, outgassing-safe
   materials) as relevant background the assistant should bring up when
   applicable, not a restriction on scope.
5. **Safety/liability guardrail.** For flight-critical or load-bearing
   conclusions, flag explicitly that the answer needs verification/sign-off
   from a certified ME or by analysis/test — this is a company with no ME on
   staff, and a wrong number here has real consequences.
6. **Reference data usage.** Instruct the model to prefer the curated values
   in `reference_data.py` over its own recalled numbers when they overlap
   (e.g. if asked for Al 6061-T6 yield strength, use the cheat-sheet value),
   to reduce hallucination risk on specific figures.

## Data flow

1. User types a message in the browser chat UI.
2. Frontend JS appends it to an in-memory history array, `POST`s the full
   history to `/chat`.
3. Backend prepends the system prompt + reference data, calls Gemini with
   the full history.
4. Gemini's reply is returned as JSON; frontend appends it to the display
   and the local history array.

## Error handling

If the Gemini call fails (bad key, rate limit, network issue), the backend
returns a clean error JSON (no stack traces leaked to the client); the
frontend shows an inline "something went wrong, try again" message. No
retry/backoff logic for this version — single attempt, surface the failure.

## Testing

Mock the Gemini client (same approach as Geo-Assist's mocked Ollama tests)
to verify:
- System prompt and reference data are included in every call.
- Conversation history is passed through correctly.
- The error path returns a proper error response when the mocked client
  raises.
