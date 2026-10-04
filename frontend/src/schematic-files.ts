import type { Part, Pin, Schematic } from './schematic-types';

const DRAFT_KEY = 'circuit-lab.analog-draft.v1';

function objectShape(value: unknown, allowed: string[]): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('Expected a circuit object.');
  const record = value as Record<string, unknown>;
  if (Object.keys(record).some(key => !allowed.includes(key))) throw new Error('Unknown circuit fields are not allowed.');
  return record;
}

function bounded(value: unknown, minimum: number, maximum: number, integer = false): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < minimum || value > maximum || (integer && !Number.isInteger(value))) {
    throw new Error('A component value or grid coordinate is outside the supported range.');
  }
  return value;
}

function parsePart(value: unknown): Part {
  const part = objectShape(value, ['id', 'kind', 'value', 'x', 'y', 'rotation', 'pulse', 'sine']);
  const limits: Record<string, [number, number]> = { R: [1, 1e8], C: [1e-12, 1], L: [1e-9, 100], V: [-100, 100], PULSE: [-100, 100], SIN: [0, 100], GND: [0, 0] };
  if (typeof part.id !== 'string' || !/^[a-zA-Z][a-zA-Z0-9_]{0,15}$/.test(part.id)) throw new Error('Invalid part identifier.');
  if (typeof part.kind !== 'string' || !Object.hasOwn(limits, part.kind)) throw new Error('Only R, C, L, DC, pulse, sine and ground are supported.');
  bounded(part.value, ...limits[part.kind]); bounded(part.x, 2, 38, true); bounded(part.y, 2, 22, true);
  if (![0, 90, 180, 270].includes(Number(part.rotation)) || typeof part.rotation !== 'number') throw new Error('Invalid rotation.');
  if (part.kind === 'PULSE') {
    const pulse = objectShape(part.pulse, ['period', 'width', 'delay']);
    const period = bounded(pulse.period, 1e-6, 10);
    bounded(pulse.width, period * .01, period * .99); bounded(pulse.delay, 0, 10);
  } else if (part.pulse !== undefined && part.pulse !== null) throw new Error('Unexpected pulse settings.');
  if (part.kind === 'SIN') {
    const sine = objectShape(part.sine, ['offset', 'frequency', 'phase']);
    const offset = bounded(sine.offset, -100, 100);
    bounded(sine.frequency, .001, 1e6); bounded(sine.phase, -360, 360);
    if (Math.abs(offset) + Number(part.value) > 100) throw new Error('Sine offset plus peak must stay within ±100 V.');
  } else if (part.sine !== undefined && part.sine !== null) throw new Error('Unexpected sine settings.');
  return part as unknown as Part;
}

function parsePin(value: unknown, parts: Part[]): Pin {
  const pin = objectShape(value, ['part', 'terminal']);
  const part = parts.find(part => part.id === pin.part);
  if (!part || (pin.terminal !== 0 && pin.terminal !== 1) || (part.kind === 'GND' && pin.terminal === 1)) throw new Error('A wire points to a missing terminal.');
  return { part: part.id, terminal: pin.terminal };
}

export function parseSchematic(text: string): Schematic {
  if (text.length > 8192) throw new Error('Circuit files must be at most 8 KB.');
  const parsed: unknown = JSON.parse(text);
  const envelope = objectShape(parsed, ['version', 'circuit', 'parts', 'wires', 'timing']);
  if (envelope.version !== undefined && envelope.version !== 2) throw new Error('Unsupported circuit file version.');
  if (envelope.version === 2) objectShape(parsed, ['version', 'circuit']);
  const graph = objectShape(envelope.version === 2 ? envelope.circuit : parsed, ['parts', 'wires', 'timing']);
  if (!Array.isArray(graph.parts) || graph.parts.length > 20 || !Array.isArray(graph.wires) || graph.wires.length > 40) throw new Error('Maximum: 20 parts and 40 wires.');
  const parts = graph.parts.map(parsePart);
  if (new Set(parts.map(part => part.id)).size !== parts.length) throw new Error('Part identifiers must be unique.');
  const wires = graph.wires.map(value => { const wire = objectShape(value, ['a', 'b']); return { a: parsePin(wire.a, parts), b: parsePin(wire.b, parts) }; });
  const timing = objectShape(graph.timing, ['stop', 'step']);
  const stop = bounded(timing.stop, 1e-6, 10), step = bounded(timing.step, 1e-7, 1);
  if (stop / step < 10 || stop / step > 2000) throw new Error('Choose 10–2000 simulation intervals.');
  return { parts, wires, timing: { stop, step } };
}

export function readDraft(scope: string | null): Schematic | null {
  const saved = scope ? localStorage.getItem(DRAFT_KEY + ':' + scope) : null;
  return saved ? parseSchematic(saved) : null;
}

export function saveDraft(schematic: Schematic, scope: string | null): void {
  if (scope) localStorage.setItem(DRAFT_KEY + ':' + scope, JSON.stringify({ version: 2, circuit: schematic }));
}

export function downloadJson(filename: string, contents: unknown): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(contents)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}
