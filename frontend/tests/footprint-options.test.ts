import assert from 'node:assert/strict';
import test from 'node:test';
import { footprintLabel, footprintOptions } from '../src/footprint-options.ts';
import { makePart, starterCircuit } from '../src/schematic-model.ts';
import { parseSchematic } from '../src/schematic-files.ts';

test('resistors offer through-hole and SMD; library parts offer their own packages', () => {
  const resistor = starterCircuit().parts.find(part => part.kind === 'R')!;
  assert.deepEqual(footprintOptions(resistor).map(option => option.mount), ['tht', 'smd']);
  const fet = { ...makePart('NMOS', [], 6, 6), device: 'irlz44n' };
  assert.equal(footprintLabel(footprintOptions(fet)[0]), 'TO-220-3_Vertical (through-hole)');
  assert.deepEqual(footprintOptions(makePart('PIN', [], 6, 6)), []);
});

test('circuit files keep valid footprint choices and refuse unknown ones', () => {
  const graph = starterCircuit();
  const withChoice = { ...graph, parts: graph.parts.map(part => part.kind === 'R' ? { ...part, footprint: 'r0805' } : part) };
  assert.equal(parseSchematic(JSON.stringify(withChoice)).parts.find(part => part.kind === 'R')?.footprint, 'r0805');
  const wrong = { ...graph, parts: graph.parts.map(part => part.kind === 'R' ? { ...part, footprint: 'to220' } : part) };
  assert.throws(() => parseSchematic(JSON.stringify(wrong)), /Unknown PCB footprint/);
});
