# Formatting Fixes + Verbosity Trim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix garbled rendering of numbered lists, `*` bullets, code fences, and LaTeX math in the chat UI, and trim response verbosity (padding, not substance).

**Architecture:** `static/index.html`'s `formatBody` function gets three new line-handling branches (numbered lists, `*` bullets, code fences) plus KaTeX added via CDN for math typesetting, invoked once per completed response (not on streaming deltas). `system_prompt.py` gets one additive directive.

**Tech Stack:** Same as existing project — vanilla HTML/CSS/JS, KaTeX via CDN, Python/pytest for the system prompt test.

## Global Constraints

- No JS framework, no build step — KaTeX is added as CDN `<link>`/`<script>` tags, same pattern as the existing Google Fonts links, not a bundled dependency.
- Math auto-render must only run on a completed response, never on an in-progress streaming delta (incomplete LaTeX would throw).
- The verbosity directive must not reduce derivation depth, equations, or numbers shown — only prose padding.

---

### Task 1: System prompt conciseness directive

**Files:**
- Modify: `system_prompt.py`
- Modify: `tests/test_system_prompt.py`

**Interfaces:**
- `system_prompt.SYSTEM_PROMPT` (existing) gains one new paragraph; no signature change.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_system_prompt.py`:

```python
def test_instructs_cutting_padding_not_substance():
    lowered = SYSTEM_PROMPT.lower()
    assert "concise" in lowered or "padding" in lowered
    assert "every equation" in lowered or "every derivation step" in lowered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && pytest tests/test_system_prompt.py -v`
Expected: FAIL — `test_instructs_cutting_padding_not_substance` fails, current `SYSTEM_PROMPT` has no such wording.

- [ ] **Step 3: Add the directive to `system_prompt.py`**

Insert this new paragraph into `SYSTEM_PROMPT`, immediately after the existing "SHOW YOUR WORK." paragraph (before "SUBJECT BREADTH."):

```python
BE CONCISE, NOT SHALLOW.
Cut preamble, throat-clearing, and restatement of the question -- do not open by \
repeating what was asked, and do not summarize what you are about to say before saying \
it. State each step directly. This is about trimming wordiness, not depth: keep every \
equation, every derivation step, and every number -- say the same substance in fewer \
words, don't say less.

```

(Keep the triple-quoted string's `\` line-continuation style consistent with the rest of `SYSTEM_PROMPT`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_system_prompt.py -v`
Expected: PASS (8 tests — the 7 existing plus this new one)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest tests/ -v`
Expected: All tests PASS (23 total: 22 existing + 1 new).

- [ ] **Step 6: Commit**

```bash
git add system_prompt.py tests/test_system_prompt.py
git commit -m "Add conciseness directive to system prompt"
```

---

### Task 2: Frontend formatting — lists, code fences, and math

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- `formatBody(text: string) -> string` (existing function) — behavior extended, signature unchanged.
- New: a `renderMath(container: Element) -> void` helper that calls KaTeX's auto-render extension, called only after a response's final text is set (not on streaming deltas).

- [ ] **Step 1: Add KaTeX via CDN in `<head>`**

In `static/index.html`, immediately after the existing Google Fonts `<link>` tags (after the line ending `...Mono:wght@400;500&display=swap" rel="stylesheet">`), add:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
```

- [ ] **Step 2: Extend `formatBody` to handle numbered lists, `*` bullets, and code fences**

Replace the current `formatBody` function body with:

```js
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
    let listTag = null;
    let inCodeFence = false;
    let codeBuffer = [];

    const flushList = () => {
      if (listBuffer.length) {
        htmlParts.push(`<${listTag}>${listBuffer.map((li) => `<li>${li}</li>`).join('')}</${listTag}>`);
        listBuffer = [];
        listTag = null;
      }
    };

    for (const rawLine of lines) {
      const trimmed = rawLine.trim();

      if (trimmed === '```') {
        if (inCodeFence) {
          htmlParts.push(`<pre><code>${codeBuffer.join('\n')}</code></pre>`);
          codeBuffer = [];
          inCodeFence = false;
        } else {
          flushList();
          inCodeFence = true;
        }
        continue;
      }
      if (inCodeFence) {
        codeBuffer.push(rawLine);
        continue;
      }

      if (!trimmed) {
        flushList();
        continue;
      }
      if (trimmed.startsWith('VERIFY:')) {
        flushList();
        htmlParts.push(
          `<div class="flag"><span aria-hidden="true">&#9888;</span>${trimmed.slice(7).trim()}</div>`
        );
      } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (listTag && listTag !== 'ul') flushList();
        listTag = 'ul';
        listBuffer.push(trimmed.slice(2));
      } else if (/^\d+\.\s/.test(trimmed)) {
        if (listTag && listTag !== 'ol') flushList();
        listTag = 'ol';
        listBuffer.push(trimmed.replace(/^\d+\.\s/, ''));
      } else {
        flushList();
        htmlParts.push(`<p>${trimmed}</p>`);
      }
    }
    flushList();
    if (inCodeFence && codeBuffer.length) {
      htmlParts.push(`<pre><code>${codeBuffer.join('\n')}</code></pre>`);
    }
    return htmlParts.join('');
  }
```

- [ ] **Step 3: Add a `renderMath` helper and call it after a response completes**

Add this function near `formatBody`:

```js
  function renderMath(container) {
    if (window.renderMathInElement) {
      window.renderMathInElement(container, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false },
        ],
        throwOnError: false,
      });
    }
  }
```

Then, in the `form.addEventListener('submit', ...)` handler, find this existing line (the success path, after the streaming loop completes):

```js
    responseBody.innerHTML = formatBody(result.text);
```

Replace it with:

```js
    responseBody.innerHTML = formatBody(result.text);
    renderMath(responseBody);
```

Do NOT call `renderMath` inside the `onDelta` callback passed to `streamChat` — that would attempt to render incomplete/partial LaTeX on every streaming chunk and throw. Only the final, completed text gets math rendering.

- [ ] **Step 4: Run the full test suite**

Run: `source venv/bin/activate && pytest tests/ -v`
Expected: All tests PASS (23 total). This change is HTML/CSS/JS-only and shouldn't affect Python tests, but confirm nothing broke (in particular `test_root_serves_frontend` still checks for the literal string `"ME-ASSIST"`, which is unaffected by this change).

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "Add numbered-list, code-fence, and KaTeX math rendering to chat UI"
```

- [ ] **Step 6: Manual verification**

With a real `GEMINI_API_KEY` exported, run `uvicorn main:app --reload --port 8000` and open `http://127.0.0.1:8000`. Ask a question likely to produce numbered steps, inline math, and a diagram (e.g. "Walk me through finding the reaction forces and moment at a fixed support for a cantilevered bracket with a 60N equivalent load at 0.35m and a 100N point load at 0.5m — show a free-body diagram"). Confirm:
- Numbered steps render as an actual ordered list (visible numbers), not raw `1.`/`2.` text.
- Any `*`-prefixed lines render as bullets.
- Inline math (e.g. `R_{Ay} = 160` N) renders as typeset math via KaTeX once the response finishes, not as raw `$...$` text.
- Any code-fenced content (e.g. an ASCII diagram) renders in a monospace block with preserved line breaks/alignment, not literal triple-backtick characters.
- During streaming (before the response finishes), the in-progress text still displays without throwing a JS error in the browser console, even if it currently contains an unclosed `$` or code fence.
- The response is noticeably less padded/repetitive than before, while still showing full derivation steps and every number.
