/**
 * Renderer tests for formatBody.
 *
 * The bug these exist for: a blank line between numbered items used to close
 * the <ol>, so each item became its own list and every one rendered as "1.".
 * Models write numbered lists with blank lines between items constantly, so
 * this made almost every list in the app look broken.
 *
 * Run with:  node tests/test_ui_markdown.js
 */

const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(
  path.join(__dirname, '..', 'static', 'index.html'), 'utf8'
);
const js = html.split('<script>').pop().split('</script>')[0];
eval(js.slice(js.indexOf('function inlineFormat'), js.indexOf('function renderMath')));

let pass = 0, fail = 0;
function check(name, condition, detail) {
  if (condition) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name}${detail ? ' -- ' + detail : ''}`); }
}
const lists = (s) => (s.match(/<ol|<ul>/g) || []).length;
const items = (s) => (s.match(/<li>/g) || []).length;

console.log('\nMarkdown rendering\n');

let out = formatBody('1. Bearing stress\n\n2. Net section\n\n3. Tear-out');
check('blank lines between numbered items stay ONE list', lists(out) === 1,
  `got ${lists(out)} lists: ${out}`);
check('all three items are kept', items(out) === 3);

out = formatBody('1. One\n2. Two');
check('tight numbered lists still work', lists(out) === 1 && items(out) === 2);

out = formatBody('- First\n\n- Second');
check('blank lines between bullets stay ONE list', lists(out) === 1 && items(out) === 2);

out = formatBody('1) One\n\n2) Two');
check('paren-style numbering is recognised', lists(out) === 1 && items(out) === 2);

out = formatBody('1. A\n2. B\n\nSome prose.\n\n1. X\n2. Y');
check('prose between lists still separates them', lists(out) === 2,
  `got ${lists(out)}`);
check('prose survives between lists', out.includes('<p>Some prose.</p>'));

out = formatBody('3. Third\n\n4. Fourth');
check('a list starting at 3 keeps its numbering', out.includes('<ol start="3">'),
  out);

out = formatBody('1. First item\n   wrapped continuation\n\n2. Second');
check('indented continuation joins its item', items(out) === 2
  && out.includes('First item wrapped continuation'), out);

out = formatBody('- Bullet\n\n1. Number');
check('switching list type starts a new list', lists(out) === 2, out);

out = formatBody('Intro line\n\n1. One\n\n2. Two');
check('a list after a paragraph is one list', lists(out) === 1 && items(out) === 2, out);

out = formatBody('VERIFY: check this\n\n1. One\n\n2. Two');
check('the VERIFY flag still renders', out.includes('class="flag"'));
check('and does not break the list after it', items(out) === 2, out);

out = formatBody('1. Use $F = ma$\n\n2. Then **check** it');
check('inline formatting survives inside items',
  out.includes('<strong>check</strong>'), out);

out = formatBody('```\ncode block\n```\n\n1. One\n\n2. Two');
check('code fences do not break lists', items(out) === 2 && out.includes('<pre>'), out);

console.log(`\n${pass} passed, ${fail} failed\n`);
process.exit(fail ? 1 : 0);
