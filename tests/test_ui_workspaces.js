/**
 * Headless UI test for discipline workspaces.
 *
 * Each discipline must be its own conversation: switching sections hides the
 * previous transcript rather than showing it or destroying it, and the history
 * sent to the server must never carry another section's messages.
 *
 * Run with:  node tests/test_ui_workspaces.js     (requires jsdom)
 */

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const HTML = fs.readFileSync(
  path.join(__dirname, '..', 'static', 'index.html'),
  'utf8'
);

const DOMAINS = {
  domains: [
    { id: 'statics', label: 'STATICS / DYNAMICS', blurb: 'Loads', starters: ['Reaction forces?'] },
    { id: 'thermal', label: 'THERMAL', blurb: 'Heat', starters: ['Steady state temp?'] },
  ],
};

let results = { pass: 0, fail: 0 };

function check(name, condition, detail) {
  if (condition) {
    results.pass += 1;
    console.log(`  PASS  ${name}`);
  } else {
    results.fail += 1;
    console.log(`  FAIL  ${name}${detail ? ' -- ' + detail : ''}`);
  }
}

function sseBody(events) {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('');
}

const STORE = {};
let SERVER_SESSION = 'session-one';

async function boot(opts = {}) {
  const sent = [];
  if (opts.freshStorage) for (const k of Object.keys(STORE)) delete STORE[k];

  const dom = new JSDOM(HTML, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://127.0.0.1:8000/',
    beforeParse(window) {
      window.fetch = (url, opts) => {
        const body = opts && opts.body ? JSON.parse(opts.body) : null;
        if (String(url).startsWith('/domains')) {
          return Promise.resolve({ json: () => Promise.resolve(DOMAINS) });
        }
        if (String(url).startsWith('/model-info')) {
          return Promise.resolve({
            json: () => Promise.resolve({
              server_session: SERVER_SESSION,
              provider: 'groq', name: 'Groq', model: 'llama-3.3-70b-versatile',
              free: true, chain: ['groq'], free_remaining: 14400, free_limit: 14400,
              free_tiers: {}, resets_at: null,
              configured: { gemini: false, groq: true, anthropic: false, openai: false },
            }),
          });
        }
        if (String(url).startsWith('/chat')) {
          sent.push(body);
          const text = sseBody([
            { provider: { provider: 'groq', name: 'Groq', model: 'llama-3.3-70b-versatile', free: true } },
            { delta: `reply to "${body.history[body.history.length - 1].content}"` },
            { usage: { provider: 'groq', model: 'x', input_tokens: 10, output_tokens: 5,
                       conversation: { cost_usd: 0, turns: 1 }, free_remaining: 14399 } },
            { done: true },
          ]);
          const bytes = new TextEncoder().encode(text);
          let done = false;
          return Promise.resolve({
            body: {
              getReader: () => ({
                read: () => {
                  if (done) return Promise.resolve({ done: true });
                  done = true;
                  return Promise.resolve({ value: bytes, done: false });
                },
              }),
            },
          });
        }
        return Promise.resolve({ json: () => Promise.resolve({}) });
      };
      window.TextDecoder = require('util').TextDecoder;
      window.TextEncoder = require('util').TextEncoder;
      // Shared across simulated page loads, so a "refresh" sees saved state.
      Object.defineProperty(window, 'localStorage', {
        value: {
          getItem: (k) => (k in STORE ? STORE[k] : null),
          setItem: (k, v) => { STORE[k] = String(v); },
          removeItem: (k) => { delete STORE[k]; },
        },
        configurable: true,
      });
    },
  });

  const { window } = dom;
  await new Promise((r) => setTimeout(r, 80));
  return { window, doc: window.document, sent };
}

const settle = () => new Promise((r) => setTimeout(r, 60));

async function ask(doc, window, text) {
  const input = doc.getElementById('input');
  input.value = text;
  doc.getElementById('input-form').dispatchEvent(
    new window.Event('submit', { bubbles: true, cancelable: true })
  );
  await settle();
}

function activePane(doc) {
  return doc.querySelector('.log__pane.is-active');
}

function visibleQueries(doc) {
  const pane = activePane(doc);
  if (!pane) return [];
  return [...pane.querySelectorAll('.entry--query .entry__body')].map((e) =>
    e.textContent.trim()
  );
}

function clickSection(doc, window, id) {
  const btn = doc.querySelector(`.section[data-domain="${id}"] .launcher`);
  btn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
}

/**
 * Static CSS guards. jsdom has no layout engine, so these check the rules that
 * make the layout correct rather than measuring pixels. The bug they guard
 * against: a flex item defaults to min-height:auto and refuses to shrink below
 * its content, so the column outgrows the viewport, the input bar is pushed
 * off the bottom, and the transcript scrolls underneath it.
 */
function checkLayoutRules() {
  const css = HTML.split('<style>')[1].split('</style>')[0];

  function rule(selector) {
    const i = css.indexOf(selector + ' {');
    if (i === -1) return '';
    return css.slice(i, css.indexOf('}', i));
  }

  console.log('\nLayout invariants\n');
  check('.log can shrink below its content (min-height:0)',
    /min-height:\s*0/.test(rule('.log')));
  check('.log scrolls internally',
    /overflow-y:\s*auto/.test(rule('.log')));
  check('.main can shrink (min-height:0)',
    /min-height:\s*0/.test(rule('.main')));
  check('.console is clipped to the viewport',
    /overflow:\s*hidden/.test(rule('.console')));
  check('.console uses dvh for mobile browser chrome',
    /height:\s*100dvh/.test(rule('.console')));
  check('the input bar never shrinks',
    /flex-shrink:\s*0/.test(rule('.input-bar')));
  check('the status bar never shrinks',
    /flex-shrink:\s*0/.test(rule('.status-bar')));
  check('the discipline panel is height-bounded',
    /max-height/.test(rule('.domain-panel')));
}

(async () => {
  checkLayoutRules();

  const { window, doc, sent } = await boot({ freshStorage: true });

  console.log('\nDiscipline workspaces\n');

  // --- general area ---
  await ask(doc, window, 'general question');
  check('general question appears in the general pane',
    visibleQueries(doc).includes('general question'));

  // --- switch to a discipline ---
  clickSection(doc, window, 'statics');
  await settle();

  check('switching to a discipline clears the visible transcript',
    visibleQueries(doc).length === 0,
    `saw: ${JSON.stringify(visibleQueries(doc))}`);
  check('the discipline panel is open',
    doc.getElementById('domain-panel').classList.contains('is-on'));
  check('the status bar shows which section is active',
    doc.getElementById('domain-chip').classList.contains('is-on'));

  await ask(doc, window, 'statics question');
  check('the discipline question appears in its own pane',
    visibleQueries(doc).join('|') === 'statics question');

  const staticsCall = sent[sent.length - 1];
  check('the discipline request carries the domain',
    staticsCall.domain === 'statics', `domain=${staticsCall.domain}`);
  check('the discipline history does NOT include the general conversation',
    staticsCall.history.every((m) => !m.content.includes('general question')),
    JSON.stringify(staticsCall.history.map((m) => m.content)));
  check('the discipline has its own conversation id',
    staticsCall.conversation_id !== sent[0].conversation_id);

  // --- second discipline ---
  clickSection(doc, window, 'thermal');
  await settle();
  check('a second discipline starts empty too',
    visibleQueries(doc).length === 0);

  await ask(doc, window, 'thermal question');
  const thermalCall = sent[sent.length - 1];
  check('the second discipline is isolated from the first',
    thermalCall.history.every((m) => !m.content.includes('statics question')));

  // --- return to the first discipline ---
  clickSection(doc, window, 'statics');
  await settle();
  check('returning to a discipline restores its transcript',
    visibleQueries(doc).join('|') === 'statics question',
    `saw: ${JSON.stringify(visibleQueries(doc))}`);
  check('the answer is restored too, not just the question',
    activePane(doc).querySelectorAll('.entry--response').length === 1);

  // --- exit back to general ---
  doc.querySelector('.domain-panel__exit')
     .dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await settle();
  check('exiting a section returns to the general conversation',
    visibleQueries(doc).join('|') === 'general question',
    `saw: ${JSON.stringify(visibleQueries(doc))}`);
  check('the discipline panel closes on exit',
    !doc.getElementById('domain-panel').classList.contains('is-on'));

  await ask(doc, window, 'second general question');
  const generalCall = sent[sent.length - 1];
  check('the general conversation kept its own context',
    generalCall.history.some((m) => m.content === 'general question'));
  check('the general request carries no domain',
    generalCall.domain === null, `domain=${generalCall.domain}`);
  check('the general conversation id is unchanged',
    generalCall.conversation_id === sent[0].conversation_id);

  // --- only one pane visible at a time ---
  check('exactly one pane is visible',
    doc.querySelectorAll('.log__pane.is-active').length === 1);
  check('all three transcripts still exist in the DOM',
    doc.querySelectorAll('.log__pane').length === 3);

  // --- persistence across a refresh ---
  console.log('\nPersistence across refresh\n');

  const reloaded = await boot();
  await settle();

  const rQueries = visibleQueries(reloaded.doc);
  check('the transcript survives a page refresh',
    rQueries.includes('general question'), `saw: ${JSON.stringify(rQueries)}`);
  check('answers are restored, not just questions',
    activePane(reloaded.doc).querySelectorAll('.entry--response').length > 0);
  check('discipline transcripts survive too',
    reloaded.doc.querySelectorAll('.log__pane').length >= 3,
    `panes: ${reloaded.doc.querySelectorAll('.log__pane').length}`);

  clickSection(reloaded.doc, reloaded.window, 'statics');
  await settle();
  check('a restored discipline still has its own transcript',
    visibleQueries(reloaded.doc).join('|') === 'statics question',
    `saw: ${JSON.stringify(visibleQueries(reloaded.doc))}`);

  await ask(reloaded.doc, reloaded.window, 'follow up');
  const afterReload = reloaded.sent[reloaded.sent.length - 1];
  check('a restored conversation keeps its context',
    afterReload.history.some((m) => m.content === 'statics question'));
  check('a restored conversation keeps its conversation id',
    afterReload.conversation_id === staticsCall.conversation_id);
  check('paid approval is NOT restored across a refresh',
    afterReload.approved_provider === null || afterReload.approved_provider === undefined);

  // --- new chat clears ---
  reloaded.window.confirm = () => true;
  reloaded.doc.getElementById('new-chat')
    .dispatchEvent(new reloaded.window.MouseEvent('click', { bubbles: true }));
  await settle();
  check('NEW clears the active conversation',
    visibleQueries(reloaded.doc).length === 0);

  await ask(reloaded.doc, reloaded.window, 'after reset');
  const afterReset = reloaded.sent[reloaded.sent.length - 1];
  check('NEW starts a fresh context',
    afterReset.history.length === 1 && afterReset.history[0].content === 'after reset');
  check('NEW starts a new conversation id',
    afterReset.conversation_id !== staticsCall.conversation_id);

  // --- transcript lifetime ---
  console.log('\nTranscript lifetime\n');

  // Same server run: a reload must keep everything.
  const sameRun = await boot();
  await settle();
  check('a reload during the same server run keeps the transcript',
    visibleQueries(sameRun.doc).length > 0,
    `saw: ${JSON.stringify(visibleQueries(sameRun.doc))}`);

  // Switching sections must not clear anything either.
  clickSection(sameRun.doc, sameRun.window, 'statics');
  await settle();
  clickSection(sameRun.doc, sameRun.window, 'statics');   // back out
  await settle();
  const generalAfterTabs = visibleQueries(sameRun.doc);
  check('moving between sections does not clear history',
    generalAfterTabs.length > 0,
    `saw: ${JSON.stringify(generalAfterTabs)}`);

  // Now simulate stopping and restarting the server.
  SERVER_SESSION = 'session-two';
  const afterRestart = await boot();
  await settle();
  check('restarting the server clears the transcript',
    visibleQueries(afterRestart.doc).length === 0,
    `saw: ${JSON.stringify(visibleQueries(afterRestart.doc))}`);
  check('and clears every section, not just the visible one',
    afterRestart.doc.querySelectorAll('.entry--query').length === 0);

  // A second reload on the SAME restarted server keeps the new transcript.
  await ask(afterRestart.doc, afterRestart.window, 'question after restart');
  const secondReload = await boot();
  await settle();
  check('the new run then persists across a reload as normal',
    visibleQueries(secondReload.doc).includes('question after restart'),
    `saw: ${JSON.stringify(visibleQueries(secondReload.doc))}`);

  console.log(`\n${results.pass} passed, ${results.fail} failed\n`);
  process.exit(results.fail ? 1 : 0);
})();
