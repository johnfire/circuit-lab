import assert from 'node:assert/strict';
import test from 'node:test';
import { BOARDS, boardOf, boardPinDescription, placeablePins } from '../src/board-library.ts';
import { makePart, partValue, pinPosition, pinsFor, starterCircuit } from '../src/schematic-model.ts';
import { parseSchematic } from '../src/schematic-files.ts';
import type { Part } from '../src/schematic-types.ts';

test('both Raspberry Pi headers list 40 pins with GPIO17 on pin 11', () => {
  for (const id of ['raspberry_pi_4', 'raspberry_pi_5']) {
    const board = boardOf(id)!;
    assert.equal(board.pins.length, 40); assert.equal(board.columns, 2);
    assert.equal(board.pins.find(pin => pin.id === '11')?.name, 'GPIO17');
    assert.ok(!placeablePins(board).some(pin => pin.kind === 'ground'));
  }
  assert.ok(BOARDS.some(board => board.id === 'arduino_uno_r3') && BOARDS.some(board => board.id === 'esp32_devkitc'));
  assert.deepEqual(boardOf('raspberry_pi_pico')!.pins.slice(0, 2).map(pin => pin.id), ['1', '40']);
});

test('a placed board pin defaults to Pi 4 GPIO17 output high with one terminal', () => {
  const pin = makePart('PIN', [], 6, 6);
  assert.equal(pin.id, 'P1'); assert.equal(partValue(pin), 'GPIO17');
  assert.equal(boardPinDescription(pin), 'Raspberry Pi 4 · pin 11 · GPIO17 · Output high');
  assert.deepEqual(pinsFor(pin).map(terminal => terminal.terminal), [0]);
  assert.deepEqual(pinPosition(pin, 0), { x: 8 * 32, y: 6 * 32 });
});

function withPin(part: Part): string {
  const graph = starterCircuit();
  return JSON.stringify({ ...graph, parts: [...graph.parts, part] });
}

test('circuit files accept valid board pins and refuse impossible ones', () => {
  const pin: Part = { id: 'P1', kind: 'PIN', value: 0, x: 4, y: 4, rotation: 0, board_pin: { board: 'raspberry_pi_5', pin: '12', mode: 'input_pull_up' } };
  assert.equal(parseSchematic(withPin(pin)).parts.at(-1)?.board_pin?.pin, '12');
  assert.throws(() => parseSchematic(withPin({ ...pin, board_pin: { ...pin.board_pin!, pin: '99' } })), /not available/);
  assert.throws(() => parseSchematic(withPin({ ...pin, board_pin: { ...pin.board_pin!, pin: '1', mode: 'output_high' } })), /cannot be set/);
  assert.throws(() => parseSchematic(withPin({ ...pin, board_pin: { ...pin.board_pin!, mode: 'pulse' } })), /circuit object|pulse/i);
  const pulsed = { ...pin, board_pin: { ...pin.board_pin!, mode: 'pulse' as const }, pulse: { period: .02, width: .01, delay: 0 } };
  assert.equal(parseSchematic(withPin(pulsed)).parts.at(-1)?.pulse?.period, .02);
});
