import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

// Test temporary copies, keeping both the application and the original tests intact.
const folder = mkdtempSync(join(tmpdir(), 'circuit-locale-mutations-'));
const source = readFileSync(new URL('../public/language-preference.js', import.meta.url), 'utf8');
const tests = readFileSync(new URL('../tests/locale-preference.test.ts', import.meta.url), 'utf8')
  .replace('../src/locale-preference.ts', './preference.mjs');
const mutations = [
  ['baseline', source],
  ['manual-choice', source.replace('if (explicit) return explicit;', 'if (false) return explicit;')],
  ['fallback', source.replace("return 'en';", "return 'de';")],
  ['browser-order', source.replace('of browserLanguages', 'of browserLanguages.toReversed()')],
  ['secure-cookie', source.replace("secure ? '; Secure' : ''", "''")],
  ['supported-languages', source.replace("candidate === 'de' || candidate === 'en' ? candidate : null", 'candidate ?? null')],
];
writeFileSync(join(folder, 'preference.test.mjs'), tests);
for (const [name, changed] of mutations) {
  if (name !== 'baseline' && changed === source) throw new Error('Mutation no longer matches source: ' + name);
  writeFileSync(join(folder, 'preference.mjs'), changed);
  const completed = spawnSync(process.execPath, ['--test', join(folder, 'preference.test.mjs')], { encoding: 'utf8' });
  if (completed.error) throw completed.error;
  const isBaseline = name === 'baseline';
  if (isBaseline && completed.status !== 0 || !isBaseline && completed.status === 0
    || !isBaseline && !completed.stdout.includes('AssertionError')) {
    process.stdout.write(completed.stdout + completed.stderr);
    throw new Error('Unexpected mutation outcome: ' + name);
  }
  process.stdout.write(name + ': ' + (isBaseline ? 'passed' : 'killed') + '\n');
}
