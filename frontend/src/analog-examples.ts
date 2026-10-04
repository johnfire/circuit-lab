import { starterCircuit } from './schematic-model.ts';
import type { Schematic } from './schematic-types';

/** Actual editable circuits, not canned simulation responses. */
export function sineExample(kind: 'R' | 'C' | 'L'): Schematic {
  const schematic = starterCircuit();
  const load = kind === 'C' ? 'C1' : kind === 'L' ? 'L1' : 'R2';
  return { ...schematic, timing: { stop: .8, step: .001 }, parts: schematic.parts.map(part => {
    if (part.id === 'V1') return { ...part, kind: 'SIN', pulse: null, sine: { offset: 0, frequency: 10, phase: 0 } };
    if (part.id === 'C1' && kind !== 'C') return { ...part, id: load, kind, value: kind === 'L' ? 10 : 1000 };
    return part;
  }), wires: schematic.wires.map(wire => ({ a: { ...wire.a, part: wire.a.part === 'C1' ? load : wire.a.part },
    b: { ...wire.b, part: wire.b.part === 'C1' ? load : wire.b.part } })) };
}
