import assert from 'node:assert/strict';
import test from 'node:test';
import { addWire, engineering, makePart, pinPosition, rotated, snapped, starterCircuit, wirePath } from '../src/schematic-model.ts';
import { parseSchematic, readDraft, saveDraft } from '../src/schematic-files.ts';
import { advanceTime, frameAt } from '../src/schematic-playback.ts';

test('standard parts and rotations preserve stable terminal orientation', () => {
  const graph = starterCircuit();
  const source = graph.parts[0];
  assert.deepEqual(pinPosition(source, 0), { x: source.x * 32, y: (source.y - 2) * 32 });
  assert.equal(rotated(270), 0);
  assert.equal(snapped(-3, 38), 2); assert.equal(snapped(99, 38), 38);
  assert.match(wirePath(graph.wires[0], graph.parts), /^M/);
  assert.equal(makePart('R', graph.parts, 6, 6).id, 'R2');
  assert.equal(makePart('PULSE', graph.parts, 6, 6).id, 'V2');
  assert.equal(engineering(.000012, 'F'), '12 µF');
  assert.equal(engineering(-.0025, 'A'), '-2.5 mA');
});

test('explicit wiring rejects self-links and reversed duplicates', () => {
  const graph = starterCircuit(), wire = graph.wires[0];
  assert.throws(() => addWire(graph, wire.a, wire.a), /different terminal/);
  assert.throws(() => addWire(graph, wire.b, wire.a), /already connected/);
  const changed = addWire({ ...graph, wires: [] }, wire.a, wire.b);
  assert.equal(changed.wires.length, 1); assert.equal(graph.wires.length, 4);
});

test('circuit exports round trip without accepting executable fields or malformed graphs', () => {
  const graph = starterCircuit();
  assert.deepEqual(parseSchematic(JSON.stringify(graph)), graph);
  assert.throws(() => parseSchematic(JSON.stringify({ ...graph, netlist: '.include /etc/passwd' })), /Unknown/);
  assert.throws(() => parseSchematic(JSON.stringify({ ...graph, parts: [{ ...graph.parts[0], value: '5; shell' }] })), /outside/);
  assert.throws(() => parseSchematic(JSON.stringify({ ...graph, parts: [{ ...graph.parts[0], kind: '__proto__' }] })), /Only/);
  assert.throws(() => parseSchematic(JSON.stringify({ ...graph, timing: { stop: 1, step: .000001 } })), /intervals/);
  assert.throws(() => parseSchematic('x'.repeat(8193)), /8 KB/);
});

test('playback selects synchronized frames and advances by simulated seconds per wall second', () => {
  const times = [0, .001, .002, .003];
  assert.equal(frameAt(times, .0018), 1); assert.equal(frameAt(times, 10), 3);
  assert.equal(advanceTime(0, 1, .001, [0, .003], false), .001);
  assert.equal(advanceTime(.002, 10, .001, [0, .003], false), .003);
  assert.ok(Math.abs(advanceTime(.002, 2, .001, [0, .003], true) - .001) < 1e-12);
  assert.equal(advanceTime(.001, -1, .001, [0, .003], false), .001);
});

test('browser drafts are separate for each account scope and unscoped drafts are never stored', () => {
  const storage = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value),
  } });
  saveDraft(starterCircuit(), 'person-one');
  assert.deepEqual(readDraft('person-one'), starterCircuit());
  assert.equal(readDraft('person-two'), null); assert.equal(readDraft(null), null);
  saveDraft(starterCircuit(), null); assert.equal(storage.size, 1);
});
