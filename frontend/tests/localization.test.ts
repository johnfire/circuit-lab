import assert from 'node:assert/strict';
import test from 'node:test';
import { localization } from '../src/localization.ts';
import { message, displayMessage, LocalizedFailure, failureMessage } from '../src/display-message.ts';
import { parseMessage, reportText } from '../src/report-localization.ts';
import { formatMeasurement } from '../src/display-numbers.ts';
import { PART_NAMES } from '../src/schematic-model.ts';
import { BLOCKS } from '../src/block-library.ts';
import { LIBRARY_PARTS } from '../src/part-library.ts';

test('already-created messages and catalogue views change language without changing electrical data', async () => {
  const savedNotice = message('shared-circuit.private_until_you_explicitly_share');
  const failure = new LocalizedFailure('schematic-model.those_terminals_are_already_connected');
  const graph = JSON.stringify(BLOCKS[0].circuit);
  await localization.changeLanguage('de');
  assert.equal(PART_NAMES.R, 'Widerstand');
  assert.equal(formatMeasurement(1234.5), '1235');
  assert.equal(formatMeasurement(1.2345), '1,235');
  assert.equal(displayMessage(savedNotice), 'Privat, bis du ausdrücklich freigibst.');
  assert.equal(displayMessage(failureMessage(failure)), 'Diese Anschlüsse sind bereits verbunden.');
  assert.equal(BLOCKS[0].name, 'LED an einem Pi-GPIO-Pin');
  assert.equal(LIBRARY_PARTS[0].description, 'Allzweck-NPN-Transistor, bis etwa 600 mA');
  assert.equal(JSON.stringify(BLOCKS[0].circuit), graph);
  await localization.changeLanguage('en');
  assert.equal(PART_NAMES.R, 'Resistor');
  assert.equal(formatMeasurement(1.2345), '1.235');
  assert.equal(BLOCKS[0].name, 'LED on a Pi GPIO pin');
  assert.equal(displayMessage(savedNotice), 'Private until you explicitly share.');
});

test('untrusted message envelopes are bounded and validated, legacy evidence remains readable', () => {
  assert.equal(parseMessage({ key: 'unknown', values: {} }), null);
  assert.equal(parseMessage({ key: 'common.language', values: { numeric: Infinity } }), null);
  assert.equal(parseMessage({ key: 'common.language', values: [] }), null);
  assert.equal(reportText('legacy warning', null), 'legacy warning');
  assert.equal(reportText('old label', { key: 'common.language', values: {} }), 'Language');
  const injected = message('shared-circuit.unsent_edits_remain_local', { reason: '<script>bad()</script>' });
  assert.equal(displayMessage(injected), 'Unsent edits remain local. <script>bad()</script>');
});
