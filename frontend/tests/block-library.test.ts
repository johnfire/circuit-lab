import assert from 'node:assert/strict';
import test from 'node:test';
import { BLOCKS, freeIdentifier, freeSpot, mergeBlock } from '../src/block-library.ts';
import { parseSchematic } from '../src/schematic-files.ts';
import { starterCircuit } from '../src/schematic-model.ts';

test('every library block is a valid circuit file the browser accepts', () => {
  assert.ok(BLOCKS.length >= 10);
  for (const block of BLOCKS) assert.equal(parseSchematic(JSON.stringify(block.circuit)).parts.length, block.circuit.parts.length, block.id);
});

test('ids are renamed with the same rule as the server', () => {
  assert.equal(freeIdentifier('R1', new Set(['R1', 'R2'])), 'R3');
  assert.equal(freeIdentifier('RPD', new Set(['RPD'])), 'RPD1');
  assert.equal(freeIdentifier('Q1', new Set(['R1'])), 'Q1');
});

test('inserting a block keeps the existing circuit, renames clashes and finds clear space', () => {
  const circuit = starterCircuit();
  const led = BLOCKS.find(block => block.id === 'pi_gpio_led')!;
  const spot = freeSpot(circuit, led)!;
  const merged = mergeBlock(circuit, led, spot.column, spot.row);
  assert.deepEqual(merged.parts.slice(0, 4), circuit.parts);
  assert.deepEqual(merged.parts.slice(4).map(part => part.id), ['P1', 'R2', 'D1', 'G2']);
  assert.ok(merged.wires.some(wire => wire.a.part === 'P1' && wire.b.part === 'R2'));
  for (const part of merged.parts.slice(4)) {
    assert.ok(circuit.parts.every(existing => Math.abs(existing.x - part.x) > 2 || Math.abs(existing.y - part.y) > 2), part.id);
  }
  assert.throws(() => mergeBlock(circuit, led, 37, 21), /doesn't fit/);
});

test('a crowded grid still gets the block, at the spot with the fewest collisions', () => {
  const wide = BLOCKS.find(block => block.id === 'pi_npn_led_switch')!;
  const spot = freeSpot(starterCircuit(), wide)!;
  assert.ok(spot.overlaps > 0 && spot.overlaps < starterCircuit().parts.length);
  assert.equal(mergeBlock(starterCircuit(), wide, spot.column, spot.row).parts.length, 4 + wide.circuit.parts.length);
});
