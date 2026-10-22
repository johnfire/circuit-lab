import assert from 'node:assert/strict';
import test from 'node:test';
import { LIBRARY_PARTS, libraryPart, terminalLetter, voltageReferenceTerminal } from '../src/part-library.ts';
import { makePart, partValue, pinPosition, pinsFor, starterCircuit } from '../src/schematic-model.ts';
import { parseSchematic } from '../src/schematic-files.ts';
import type { Part, Schematic } from '../src/schematic-types.ts';

test('the browser library lists real parts with trust levels for every device kind', () => {
  assert.ok(LIBRARY_PARTS.length >= 20);
  for (const kind of ['D', 'NMOS', 'PMOS', 'NPN', 'PNP']) assert.ok(LIBRARY_PARTS.some(part => part.kind === kind), kind);
  assert.ok(LIBRARY_PARTS.every(part => part.trust === 'draft' || part.trust === 'verified'));
  assert.deepEqual(libraryPart('irlz44n')?.terminals, ['drain', 'gate', 'source']);
});

test('placing a transistor picks a library part and lays out three labelled terminals', () => {
  const fet = makePart('NMOS', [], 10, 10);
  assert.equal(fet.id, 'Q1'); assert.equal(fet.value, 0);
  assert.equal(libraryPart(fet.device)?.kind, 'NMOS');
  assert.equal(partValue(fet), libraryPart(fet.device)?.name);
  assert.deepEqual(pinsFor(fet).map(pin => pin.terminal), [0, 1, 2]);
  assert.deepEqual(pinPosition(fet, 0), { x: 11 * 32, y: 8 * 32 });
  assert.deepEqual(pinPosition(fet, 1), { x: 8 * 32, y: 10 * 32 });
  assert.deepEqual(pinPosition(fet, 2), { x: 11 * 32, y: 12 * 32 });
  assert.deepEqual([0, 1, 2].map(terminal => terminalLetter(fet, terminal)), ['D', 'G', 'S']);
  assert.equal(voltageReferenceTerminal('NPN'), 2); assert.equal(voltageReferenceTerminal('D'), 1);
  const diode = makePart('D', [fet], 4, 4);
  assert.equal(diode.id, 'D1'); assert.deepEqual(pinsFor(diode).map(pin => pin.terminal), [0, 1]);
});

function withDevice(part: Part, wires: Schematic['wires'] = []): string {
  const graph = starterCircuit();
  return JSON.stringify({ ...graph, parts: [...graph.parts, part], wires: [...graph.wires, ...wires] });
}

test('circuit files accept library devices and reject unknown or mismatched ones', () => {
  const fet: Part = { id: 'Q1', kind: 'NMOS', value: 0, x: 20, y: 12, rotation: 0, device: 'irlz44n' };
  const parsed = parseSchematic(withDevice(fet, [{ a: { part: 'Q1', terminal: 2 }, b: { part: 'G1', terminal: 0 } }]));
  assert.equal(parsed.parts.at(-1)?.device, 'irlz44n');
  assert.throws(() => parseSchematic(withDevice({ ...fet, device: 'made_up' })), /not available/);
  assert.throws(() => parseSchematic(withDevice({ ...fet, device: '1n4148' })), /is not a NMOS/);
  assert.throws(() => parseSchematic(withDevice({ ...fet, kind: 'R', value: 100 })), /Only library devices/);
  assert.throws(() => parseSchematic(JSON.stringify({ ...starterCircuit(), wires: [
    { a: { part: 'R1', terminal: 2 }, b: { part: 'G1', terminal: 0 } }] })), /missing terminal/);
});

test('op-amps and regulators get their own terminal layouts, labels and reference terminals', () => {
  const amplifier = makePart('OPAMP', [], 10, 10);
  assert.equal(amplifier.id, 'U1'); assert.equal(libraryPart(amplifier.device)?.kind, 'OPAMP');
  assert.deepEqual(pinsFor(amplifier).map(pin => pin.terminal), [0, 1, 2, 3, 4]);
  assert.deepEqual([0, 1, 2, 3, 4].map(terminal => terminalLetter(amplifier, terminal)), ['OUT', '+', '−', 'V+', 'V−']);
  assert.deepEqual(pinPosition(amplifier, 0), { x: 13 * 32, y: 10 * 32 });
  assert.deepEqual(pinPosition(amplifier, 3), { x: 10 * 32, y: 8 * 32 });
  assert.equal(voltageReferenceTerminal('OPAMP'), 4);
  const regulator = makePart('REG', [amplifier], 20, 10);
  assert.equal(regulator.id, 'U2');
  assert.deepEqual([0, 1, 2].map(terminal => terminalLetter(regulator, terminal)), ['OUT', 'IN', 'G/A']);
  assert.equal(voltageReferenceTerminal('REG'), 2);
  const circuit = { ...starterCircuit(), parts: [...starterCircuit().parts, amplifier] };
  assert.equal(parseSchematic(JSON.stringify({ ...circuit, wires: [...circuit.wires,
    { a: { part: 'U1', terminal: 4 }, b: { part: 'G1', terminal: 0 } }] })).wires.at(-1)?.a.terminal, 4);
  assert.throws(() => parseSchematic(JSON.stringify({ ...circuit, wires: [
    { a: { part: 'U1', terminal: 5 }, b: { part: 'G1', terminal: 0 } }] })), /missing terminal/);
});
