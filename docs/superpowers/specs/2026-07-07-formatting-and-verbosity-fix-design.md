# Formatting Fixes + Verbosity Trim

**Status:** Approved by user, ready for implementation.

## Why

Manual testing of the mission-control redesign surfaced two real issues in actual Gemini output:
1. `formatBody` in `static/index.html` only recognizes `**bold**`, `` `inline code` ``, and `- ` bullets. Gemini's real answers also include numbered lists (`1.`, `2.`...), `*`-prefixed bullets, LaTeX math (`$R_{Ay} = 160$ N`), and triple-backtick code fences (used for ASCII free-body diagrams) — none of which are handled, so they render as raw, garbled text (stray `$`, `\`, and backtick characters visible).
2. Responses are too verbose — not in derivation depth (that's the point of the app), but in padding/restatement around the substance.

## 1. Frontend formatting (`static/index.html`)

- **Numbered lists:** lines matching `^\d+\.\s` are collected into an `<ol>`, parallel to the existing `<ul>` handling for `- ` lines.
- **`*`-prefixed bullets:** lines starting with `* ` are treated the same as `- ` lines (both feed the same list buffer).
- **Code fences:** a line that is exactly ` ``` ` toggles a "inside code fence" state; while inside, raw lines (no inline-markdown processing) are collected into a single `<pre><code>` block until the closing ` ``` `.
- **Math rendering (KaTeX):** add KaTeX's CSS + JS + auto-render extension via CDN `<link>`/`<script>` tags in `<head>`, same pattern as the existing Google Fonts links. `formatBody` continues to emit the raw `$...$`/`$$...$$` delimiters as plain text (no change needed there — KaTeX's auto-render extension scans rendered DOM text for these delimiters and replaces them in place). Auto-render is invoked only after a response finishes (on the `result.ok` path, after `responseBody.innerHTML = formatBody(result.text)`), never on intermediate streaming deltas — rendering incomplete LaTeX mid-stream (e.g. a cut-off `$R_{A`) would throw. During streaming, partially-arrived math stays as plain unrendered text; it snaps to typeset math the instant the response completes.

## 2. System prompt verbosity (`system_prompt.py`)

Add one new directive (additive, not replacing "SHOW YOUR WORK"): instruct the model to cut preamble, throat-clearing, and restatement of the question, and to state each step directly — while explicitly preserving every equation, derivation step, and number. `tests/test_system_prompt.py` gets one new test asserting this directive is present (e.g. asserting a keyword like "concise" or "padding" appears, following the existing test-per-facet pattern in that file).

## Testing

- `tests/test_system_prompt.py`: one new test for the conciseness directive.
- No JS test framework exists in this project (unchanged constraint) — the formatting changes are verified manually: send a question that produces a numbered list, a `*` bullet list, an ASCII diagram in a code fence, and inline math, and confirm each renders correctly (ordered list numbers, bullets, monospace preserved-whitespace block, and typeset math respectively) once the response completes.

## Out of scope

- No change to streaming pacing/chunk buffering (user confirmed the "too fast" complaint was about verbosity, not chunk burstiness).
- No change to the `VERIFY:` flag parsing/styling, which already works correctly.
