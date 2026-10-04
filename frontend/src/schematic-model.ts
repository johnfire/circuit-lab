import type { Part, PartKind, Pin, Rotation, Schematic, Wire } from './schematic-types';
import componentCatalog from '../../circuits/components.json' with { type: 'json' };

export const GRID = 32;
export const PART_NAMES: Record<PartKind, string> = {
  R: 'Resistor', C: 'Capacitor', L: 'Inductor', V: 'DC source', PULSE: 'Pulse source', SIN: 'Sine source', GND: 'Ground',
};
export const STANDARD_VALUES = Object.fromEntries(Object.entries(componentCatalog)
  .map(([kind, definition]) => [kind, definition.standard_values])) as Record<PartKind, number[]>;

export function engineering(value: number, unit = ''): string {
  if (value === 0) return '0 ' + unit;
  const prefixes: [number, string][] = [[1e6, 'M'], [1e3, 'k'], [1, ''], [1e-3, 'm'], [1e-6, 'µ'], [1e-9, 'n'], [1e-12, 'p']];
  const [scale, prefix] = prefixes.find(([scale]) => Math.abs(value) >= scale) ?? [1e-12, 'p'];
  return Number((value / scale).toPrecision(4)) + ' ' + prefix + unit;
}

export function partValue(part: Part): string {
  const units: Record<PartKind, string> = { R: 'Ω', C: 'F', L: 'H', V: 'V', PULSE: 'V pulse', SIN: 'V peak sine', GND: 'V reference' };
  return engineering(part.value, units[part.kind]);
}

export function pinKey(pin: Pin): string { return pin.part + ':' + pin.terminal; }
export function samePin(first: Pin, second: Pin): boolean { return pinKey(first) === pinKey(second); }
export function pinsFor(part: Part): Pin[] {
  return part.kind === 'GND' ? [{ part: part.id, terminal: 0 }]
    : [{ part: part.id, terminal: 0 }, { part: part.id, terminal: 1 }];
}

export function pinPosition(part: Part, terminal: 0 | 1): { x: number; y: number } {
  const offset = part.kind === 'GND' ? { x: 0, y: -2 } : { x: terminal === 0 ? -2 : 2, y: 0 };
  const angle = part.rotation * Math.PI / 180;
  return { x: (part.x + Math.round(offset.x * Math.cos(angle) - offset.y * Math.sin(angle))) * GRID,
    y: (part.y + Math.round(offset.x * Math.sin(angle) + offset.y * Math.cos(angle))) * GRID };
}

export function wirePath(wire: Wire, parts: Part[]): string {
  const first = parts.find(part => part.id === wire.a.part);
  const second = parts.find(part => part.id === wire.b.part);
  if (!first || !second) return '';
  const a = pinPosition(first, wire.a.terminal), b = pinPosition(second, wire.b.terminal);
  const middle = Math.round((a.x + b.x) / (2 * GRID)) * GRID;
  return 'M' + a.x + ',' + a.y + ' H' + middle + ' V' + b.y + ' H' + b.x;
}

export function addWire(schematic: Schematic, a: Pin, b: Pin): Schematic {
  if (samePin(a, b)) throw new Error('Choose a different terminal to complete the wire.');
  if (schematic.wires.length >= 40) throw new Error('This prototype supports up to 40 wires.');
  if (schematic.wires.some(wire => (samePin(wire.a, a) && samePin(wire.b, b)) || (samePin(wire.a, b) && samePin(wire.b, a)))) {
    throw new Error('Those terminals are already connected.');
  }
  return { ...schematic, wires: [...schematic.wires, { a, b }] };
}

export function makePart(kind: PartKind, parts: Part[], x: number, y: number): Part {
  if (parts.length >= 20) throw new Error('This prototype supports up to 20 parts.');
  const prefix = kind === 'GND' ? 'G' : kind === 'PULSE' || kind === 'SIN' ? 'V' : kind;
  let suffix = 1;
  while (parts.some(part => part.id === prefix + suffix)) suffix++;
  const defaults: Record<PartKind, number> = { R: 1000, C: 10e-6, L: 10e-3, V: 5, PULSE: 5, SIN: 5, GND: 0 };
  return { id: prefix + suffix, kind, value: defaults[kind], x, y, rotation: kind === 'GND' ? 0 : 90,
    ...(kind === 'PULSE' ? { pulse: { period: .1, width: .05, delay: .001 } } : {}),
    ...(kind === 'SIN' ? { sine: { offset: 0, frequency: 10, phase: 0 } } : {}) };
}

export function rotated(rotation: Rotation): Rotation { return ((rotation + 90) % 360) as Rotation; }
export function snapped(value: number, maximum: number): number { return Math.max(2, Math.min(maximum, Math.round(value))); }

export function starterCircuit(): Schematic {
  return { parts: [
    { id: 'V1', kind: 'PULSE', value: 5, x: 6, y: 10, rotation: 90, pulse: { period: .1, width: .05, delay: .001 } },
    { id: 'R1', kind: 'R', value: 1000, x: 17, y: 8, rotation: 0 },
    { id: 'C1', kind: 'C', value: 10e-6, x: 28, y: 10, rotation: 90 },
    { id: 'G1', kind: 'GND', value: 0, x: 17, y: 18, rotation: 0 },
  ], wires: [
    { a: { part: 'V1', terminal: 0 }, b: { part: 'R1', terminal: 0 } },
    { a: { part: 'R1', terminal: 1 }, b: { part: 'C1', terminal: 0 } },
    { a: { part: 'C1', terminal: 1 }, b: { part: 'G1', terminal: 0 } },
    { a: { part: 'G1', terminal: 0 }, b: { part: 'V1', terminal: 1 } },
  ], timing: { stop: .08, step: .0001 } };
}
