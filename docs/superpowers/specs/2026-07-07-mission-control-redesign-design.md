# ME Assistant — Mission Control Redesign + Streaming

**Status:** Approved by user, ready for implementation planning.

## Why

The original "engineering log sheet" theme (navy blueprint, serif prose, drawing title block) shipped in the initial 7-task plan and passed manual verification, but the user decided the overall concept didn't fit ("not the biggest fan of the vibe... the whole concept"). Separately, the user wants real generative streaming instead of the current wait-for-the-whole-response-then-paste-it-in behavior. Three visual directions were mocked up (mission-control, Frutiger Aero, deliberately-generic chatbot); the user chose mission-control.

This spec supersedes Task 6 (frontend) of the original plan and extends Task 4/5 (llm.py, main.py) to support streaming. Tasks 1–4 (config, reference data, system prompt, non-streaming `get_response`) remain valid as-is except where noted.

## Global constraints (unchanged from original plan)

- No RAG/document grounding, no conversation persistence beyond the browser tab, no auth, no JS framework/build step.
- `GEMINI_MODEL` env var configurable, default `gemini-2.5-flash` (already changed from the original `gemini-2.5-pro` default after a quota issue — see `config.py`).
- `VERIFY:` flags must remain visually distinct — this is a semantic safety signal, not decoration, and must **not** share color with any decorative accent.

## 1. Backend: streaming `/chat`

**Endpoint contract change:** `POST /chat` changes from a JSON-in/JSON-out endpoint to a Server-Sent-Events stream. This replaces the existing 200/502 JSON contract entirely (no versioned/parallel endpoint) — the whole point is the frontend never gets a response it has to wait on silently.

- Request body: unchanged — `{"history": [{"role": "user"|"model", "content": str}, ...]}`.
- Response: `text/event-stream`. Each SSE message is `data: <json>\n\n` where `<json>` is one of:
  - `{"delta": "<text chunk>"}` — a piece of the reply as it's generated.
  - `{"done": true}` — stream finished successfully, no more events follow.
  - `{"error": "<message>"}` — something failed (bad key, quota, network); this is the **only** event in the stream when it happens, no `delta`/`done` before it.
- HTTP status is always `200` once headers are sent (SSE can't renegotiate status mid-stream) — success/failure is communicated by which event arrives, not by status code. This is a deliberate break from the old 502-on-failure contract; `tests/test_main.py` will be rewritten to assert on stream content instead of status code for the failure case.

**`llm.py` addition:** a new `get_response_stream(history: list[dict]) -> Iterator[str]` that yields text deltas, using `google-genai`'s streaming chat call (the exact method — e.g. `chat.send_message_stream`— gets confirmed against the installed SDK during implementation, the same way the non-streaming `get_response` API surface was confirmed in Task 4; tests mock at the same `llm.genai.Client` boundary). Same `LLMError` wrapping as today: any exception from the SDK during streaming raises `LLMError`, which `main.py` catches and turns into a single `{"error": ...}` SSE event. The existing non-streaming `get_response` can be deleted once nothing calls it — the frontend is the only consumer and it's moving to the streaming endpoint.

## 2. Frontend: Mission Control theme

**Palette:**

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0A0E12` | page background |
| `--panel` | `#10161C` | ops panel background |
| `--grid-line` | `#1E2830` | hairline borders |
| `--text` | `#C8D6DC` | primary text |
| `--text-dim` | `#5C707A` | secondary/status labels |
| `--text-dimmer` | `#3D4C56` | tertiary labels, footer |
| `--accent` | `#2FD8C4` | live/transmitting state, user query label, send button |
| `--warn` | `#E8A33D` | **`VERIFY:` flags only** — no other decorative use |
| `--danger` | `#FF5C5C` | error entries |

**Type:** `Space Grotesk` (wordmark/section labels only, used sparingly), `IBM Plex Sans` (response/query prose — replaces the old serif), `IBM Plex Mono` (status bar, ops panel labels, entry index numbers, quick-launcher labels).

**Layout — two-column console:**

- **Left ops panel**, fixed ~216px, `--panel` background, border-right hairline.
  - GeoCosmos logo as a light nameplate chip (`#F4F2EC` background — the source PNG is not transparent, so it always sits on its own light chip rather than directly on the dark panel) at the top.
  - "QUICK LAUNCH" mono label, then 8 quick-launcher buttons, one per ME domain: **Statics/Dynamics, Materials, Thermal, Composites, Vibrations, GD&T, Fasteners, Manufacturing**. Clicking one populates (does not auto-send) the input textarea with a starter question for that domain, so the user can edit before sending:
    - Statics/Dynamics → "How do I calculate the reaction forces on this bracket?"
    - Materials → "What material would you recommend for this part, and why?"
    - Thermal → "How will this component behave under thermal cycling in orbit?"
    - Composites → "What layup would you use for this panel, and what failure theory applies?"
    - Vibrations → "What's the expected response of this bracket to launch vibration?"
    - GD&T → "What GD&T callouts should I use on this drawing?"
    - Fasteners → "What fastener size and torque should I use here?"
    - Manufacturing → "Is this part design-for-manufacturability friendly?"
  - Footer: small "ME-ASSIST / GEOCOSMOS" mono caption, bottom-aligned.
- **Right main pane:**
  - Status bar (top, hairline border below): app name (Space Grotesk), `MODEL: <value of GEMINI_MODEL>`, a live status word — `IDLE` normally, `TRANSMITTING` (accent color, pulsing dot) while a stream is in progress — and, once a response completes, elapsed latency for that response (e.g. `LAT: 1.4s`).
  - Log: entries styled as `>> QUERY` / `>> RESPONSE` (mono label + index number), replacing the old `001 QUERY` log-sheet numbering style but keeping the same numbering *concept* (still numbered per exchange).
  - While a response is streaming: text appended incrementally as `delta` events arrive; a blinking block cursor (`--accent` colored) sits at the end of the in-progress text; status bar reads `TRANSMITTING`. On `done`, cursor is removed and latency is recorded. On `error`, the partial response (if any) is discarded and a `--danger`-bordered `ERROR` entry appears with the message, same as today.
  - **Interrupted stream (no `done` or `error` ever received):** because the HTTP status is always 200 once streaming starts, a dropped connection (server crash, network loss, proxy timeout) looks identical to a normal in-progress response unless the frontend explicitly checks for it. When the underlying stream closes/ends without having received a `done` or `error` event, the frontend treats that as its own error case — discards the partial text, removes the cursor, and shows a `--danger`-bordered `ERROR` entry ("Response was interrupted — try again") rather than silently keeping whatever partial text had arrived. This is load-bearing: without it, a mid-stream failure would render as a shorter-than-expected but otherwise normal-looking answer, with no indication anything went wrong.
  - `VERIFY:` flags: same parsing rule as today (`formatBody` special-cases lines starting with `VERIFY:`), rendered as an amber-left-border box using `--warn`.
  - Input bar: unchanged behavior (Enter to send, Shift+Enter for newline, auto-growing textarea), restyled to the console palette.

**Responsive (< 640px):** the ops panel is hidden by default; a small toggle control in the status bar opens it as a slide-over drawer (overlay, dismiss on selecting a launcher or tapping outside). Main pane (status bar, log, input) remains fully usable at mobile width without horizontal scroll, per the original plan's mobile verification step.

**Accessibility:** focus-visible outlines on launcher buttons, textarea, and send button; `aria-live="polite"` on the log region (unchanged from today); `prefers-reduced-motion` disables the status-dot pulse and cursor blink (shown static instead of removed, so the state is still visible).

## Testing

- `tests/test_main.py`: rewrite the two `/chat` tests to assert on SSE event content (`delta`/`done`/`error` sequences) instead of JSON status codes; `test_root_serves_frontend` stays as-is (still checks `"ME-ASSIST"` appears, which the new status bar / footer still contain).
- `tests/test_llm.py`: add tests for `get_response_stream` (mocked at the same `llm.genai.Client` boundary as `get_response`), remove tests for `get_response` once it's deleted.
- New: a small test or two for the SSE event framing helper in `main.py` (e.g. a `_sse(payload: dict) -> str` formatter), if one is extracted — implementation detail, decided during planning.
- Frontend: a test/manual check that a stream ending with no `done` or `error` event (connection dropped mid-response) renders the "Response was interrupted" `ERROR` entry rather than silently displaying the partial text as if it were complete.
- Manual end-to-end verification (replaces the original Task 7 checklist items that reference the old visual design): confirm streaming text actually appears incrementally (not pasted all at once), `TRANSMITTING`/`IDLE` status transitions, latency readout, all 8 quick-launchers populate the correct starter text, `VERIFY:` flag renders in amber, mobile width (<640px) hides the ops panel behind a working toggle, and an invalid API key produces a visible red `ERROR` entry via the `error` SSE event rather than a silent failure or crash.

## Out of scope

- No changes to `config.py`, `reference_data.py`, or `system_prompt.py` beyond what's already shipped.
- No multi-session/thread history, no persisting the ops-panel state, no settings UI.
- Frutiger Aero and generic-chatbot mockups are discarded, not built.
