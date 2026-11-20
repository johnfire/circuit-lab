const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function hasTranslation(node) {
  if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'translate') return true;
  return ts.forEachChild(node, hasTranslation) || false;
}

test('visible JSX and accessibility labels use message keys; circuit symbols stay technical', () => {
  const technical = new Set(['Circuit', 'Lab', 'CIRCUIT LAB', 'REG', 'I', 'V', 'ΔV', '(ms)', 'ms · ngspice']);
  const folder = path.join(__dirname, '../src');
  const untranslated = [];
  for (const filename of fs.readdirSync(folder).filter(filename => filename.endsWith('.tsx'))) {
    const source = fs.readFileSync(path.join(folder, filename), 'utf8');
    const tree = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    function inspect(node) {
      if (ts.isJsxText(node) && /[A-Za-z]/.test(node.text) && !technical.has(node.text.trim()))
        untranslated.push(filename + ': ' + node.text.trim());
      if (ts.isJsxAttribute(node) && ['aria-label', 'title', 'placeholder'].includes(node.name.getText(tree))
        && node.initializer && ts.isStringLiteral(node.initializer) && /[A-Za-z]/.test(node.initializer.text))
        untranslated.push(filename + ': ' + node.initializer.text);
      if (ts.isJsxAttribute(node) && ['className', 'id', 'name', 'value', 'transform', 'role'].includes(node.name.getText(tree))
        && node.initializer && hasTranslation(node.initializer))
        untranslated.push(filename + ': translated technical attribute ' + node.name.getText(tree));
      ts.forEachChild(node, inspect);
    }
    inspect(tree);
  }
  assert.deepEqual(untranslated, []);
});
