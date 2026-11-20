import { LocalizedFailure } from './display-message.ts';
import { isDeviceKind, libraryPart, terminalCount } from './part-library.ts';
import { boardOf } from './board-library.ts';
import { footprintOptions } from './footprint-options.ts';
import type { Part, Pin, PinMode, Schematic } from './schematic-types';
import componentCatalog from '../../circuits/components.json' with { type: 'json' };

const DRAFT_KEY = 'circuit-lab.analog-draft.v1';

function objectShape(value: unknown, allowed: string[]): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new LocalizedFailure("schematic-files.expected_a_circuit_object");
  const record = value as Record<string, unknown>;
  if (Object.keys(record).some(key => !allowed.includes(key))) throw new LocalizedFailure("schematic-files.unknown_circuit_fields_are_not");
  return record;
}

function bounded(value: unknown, minimum: number, maximum: number, integer = false): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < minimum || value > maximum || (integer && !Number.isInteger(value))) {
    throw new LocalizedFailure("schematic-files.a_component_value_or_grid");
  }
  return value;
}

function parsePart(value: unknown): Part {
  const part = objectShape(value, ['id', 'kind', 'value', 'x', 'y', 'rotation', 'pulse', 'sine', 'device', 'board_pin', 'footprint', 'voltage_rating']);
  const limits: Record<string, [number, number]> = Object.fromEntries(Object.entries(componentCatalog)
    .map(([kind, definition]) => [kind, [definition.minimum, definition.maximum]]));
  if (typeof part.id !== 'string' || !/^[a-zA-Z][a-zA-Z0-9_]{0,15}$/.test(part.id)) throw new LocalizedFailure("schematic-files.invalid_part_identifier");
  if (typeof part.kind !== 'string' || !Object.hasOwn(limits, part.kind)) throw new LocalizedFailure("schematic-files.only_supported_part_kinds_are");
  parseDevice(part);
  parseBoardPin(part);
  if (part.footprint !== undefined && part.footprint !== null
    && !footprintOptions(part as unknown as Part).some(option => option.id === part.footprint)) throw new LocalizedFailure("files.unknown_footprint", { part: String(part.id) });
  if (part.voltage_rating !== undefined && part.voltage_rating !== null) {
    if (part.kind !== 'C') throw new LocalizedFailure("schematic-files.only_capacitors_carry_a_voltage");
    if (typeof part.voltage_rating !== 'number' || !(part.voltage_rating > 0 && part.voltage_rating <= 1000)) throw new LocalizedFailure("schematic-files.capacitor_voltage_rating_must_be");
  }
  bounded(part.value, ...limits[part.kind]); bounded(part.x, 2, 38, true); bounded(part.y, 2, 22, true);
  if (![0, 90, 180, 270].includes(Number(part.rotation)) || typeof part.rotation !== 'number') throw new LocalizedFailure("schematic-files.invalid_rotation");
  if (part.kind === 'PULSE' || (part.kind === 'PIN' && (part.board_pin as { mode?: unknown } | null)?.mode === 'pulse')) {
    const pulse = objectShape(part.pulse, ['period', 'width', 'delay']);
    const period = bounded(pulse.period, 1e-6, 10);
    bounded(pulse.width, period * .01, period * .99); bounded(pulse.delay, 0, 10);
  } else if (part.pulse !== undefined && part.pulse !== null) throw new LocalizedFailure("schematic-files.unexpected_pulse_settings");
  if (part.kind === 'SIN') {
    const sine = objectShape(part.sine, ['offset', 'frequency', 'phase']);
    const offset = bounded(sine.offset, -100, 100);
    bounded(sine.frequency, .001, 1e6); bounded(sine.phase, -360, 360);
    if (Math.abs(offset) + Number(part.value) > 100) throw new LocalizedFailure("schematic-files.sine_offset_plus_peak_must");
  } else if (part.sine !== undefined && part.sine !== null) throw new LocalizedFailure("schematic-files.unexpected_sine_settings");
  return part as unknown as Part;
}

function parseDevice(part: Record<string, unknown>): void {
  if (!isDeviceKind(part.kind as Part['kind'])) {
    if (part.device !== undefined && part.device !== null) throw new LocalizedFailure("schematic-files.only_library_devices_diodes_transistors");
    return;
  }
  const library = libraryPart(typeof part.device === 'string' ? part.device : null);
  if (!library) throw new LocalizedFailure("schematic-files.this_circuit_uses_a_library");
  if (library.kind !== part.kind) throw new LocalizedFailure("files.device_kind", { name: library.name, kind: String(part.kind) });
}

function parseBoardPin(part: Record<string, unknown>): void {
  if (part.kind !== 'PIN') {
    if (part.board_pin !== undefined && part.board_pin !== null) throw new LocalizedFailure("schematic-files.only_board_pins_set_boardpin");
    return;
  }
  const settings = objectShape(part.board_pin, ['board', 'pin', 'mode']);
  const board = boardOf(typeof settings.board === 'string' ? settings.board : undefined);
  const pin = board?.pins.find(candidate => candidate.id === settings.pin);
  if (!board || !pin) throw new LocalizedFailure("schematic-files.this_circuit_uses_a_board");
  if (!pin.modes.includes(settings.mode as PinMode)) throw new LocalizedFailure("files.pin_mode", { pin: pin.name, mode: String(settings.mode) });
}

function parsePin(value: unknown, parts: Part[]): Pin {
  const pin = objectShape(value, ['part', 'terminal']);
  const part = parts.find(part => part.id === pin.part);
  if (!part || typeof pin.terminal !== 'number' || !Number.isInteger(pin.terminal) || pin.terminal < 0 || pin.terminal >= terminalCount(part.kind)) {
    throw new LocalizedFailure("schematic-files.a_wire_points_to_a");
  }
  return { part: part.id, terminal: pin.terminal as Pin['terminal'] };
}

export function parseSchematic(text: string): Schematic {
  if (text.length > 8192) throw new LocalizedFailure("schematic-files.circuit_files_must_be_at");
  const parsed: unknown = JSON.parse(text);
  const envelope = objectShape(parsed, ['version', 'circuit', 'parts', 'wires', 'timing']);
  if (envelope.version !== undefined && envelope.version !== 2) throw new LocalizedFailure("schematic-files.unsupported_circuit_file_version");
  if (envelope.version === 2) objectShape(parsed, ['version', 'circuit']);
  const graph = objectShape(envelope.version === 2 ? envelope.circuit : parsed, ['parts', 'wires', 'timing']);
  if (!Array.isArray(graph.parts) || graph.parts.length > 20 || !Array.isArray(graph.wires) || graph.wires.length > 40) throw new LocalizedFailure("schematic-files.maximum_20_parts_and_40");
  const parts = graph.parts.map(parsePart);
  if (new Set(parts.map(part => part.id)).size !== parts.length) throw new LocalizedFailure("schematic-files.part_identifiers_must_be_unique");
  const wires = graph.wires.map(value => { const wire = objectShape(value, ['a', 'b']); return { a: parsePin(wire.a, parts), b: parsePin(wire.b, parts) }; });
  const timing = objectShape(graph.timing, ['stop', 'step']);
  const stop = bounded(timing.stop, 1e-6, 10), step = bounded(timing.step, 1e-7, 1);
  if (stop / step < 10 || stop / step > 2000) throw new LocalizedFailure("schematic-files.choose_102000_simulation_intervals");
  return { parts, wires, timing: { stop, step } };
}

export function readDraft(scope: string | null): Schematic | null {
  const saved = scope ? localStorage.getItem(DRAFT_KEY + ':' + scope) : null;
  return saved ? parseSchematic(saved) : null;
}

export function saveDraft(schematic: Schematic, scope: string | null): void {
  if (scope) localStorage.setItem(DRAFT_KEY + ':' + scope, JSON.stringify({ version: 2, circuit: schematic }));
}

export function downloadText(filename: string, contents: string, type: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}

export function downloadJson(filename: string, contents: unknown): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(contents)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}
