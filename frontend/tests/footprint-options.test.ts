import assert from 'node:assert/strict';
import test from 'node:test';
import { footprintLabel, footprintOptions, passivePackage } from '../src/footprint-options.ts';
import { makePart, starterCircuit } from '../src/schematic-model.ts';
import { parseSchematic } from '../src/schematic-files.ts';

test('resistors offer 1/4, 1/2 and 1 W through-hole and SMD; library parts offer their own packages', () => {
  const resistor = starterCircuit().parts.find(part => part.kind === 'R')!;
  assert.deepEqual(footprintOptions(resistor).map(option => option.mount), ['tht', 'tht', 'tht', 'smd']);
  assert.deepEqual(footprintOptions(resistor).map(option => option.ratings?.power_max?.value), [0.25, 0.5, 1, 0.125]);
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

test('rating checks name the resistor or capacitor package they used', () => {
  assert.equal(passivePackage('r_axial_1w')?.ratings?.power_max?.value, 1);
  assert.equal(passivePackage('c_radial')?.dielectric, 'electrolytic');
  assert.equal(passivePackage('lm7805'), undefined);
});

test('circuit files keep a capacitor voltage rating and refuse it elsewhere or out of range', () => {
  const graph = starterCircuit();
  const rated = { ...graph, parts: graph.parts.map(part => part.kind === 'C' ? { ...part, voltage_rating: 25 } : part) };
  assert.equal(parseSchematic(JSON.stringify(rated)).parts.find(part => part.kind === 'C')?.voltage_rating, 25);
  const onResistor = { ...graph, parts: graph.parts.map(part => part.kind === 'R' ? { ...part, voltage_rating: 25 } : part) };
  assert.throws(() => parseSchematic(JSON.stringify(onResistor)), /Only capacitors/);
  const tooHigh = { ...graph, parts: graph.parts.map(part => part.kind === 'C' ? { ...part, voltage_rating: 5000 } : part) };
  assert.throws(() => parseSchematic(JSON.stringify(tooHigh)), /at most 1000 V/);
});
