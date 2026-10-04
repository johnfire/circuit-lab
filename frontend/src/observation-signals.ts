import type { ObservationReport, Pin, Probe, Schematic } from './schematic-types';

export interface Signal { key: string; label: string; unit: 'V' | 'A'; real: number[]; imaginary?: number[] }
export interface ComplexSample { real: number; imaginary: number }

export function reportAxis(report: ObservationReport): number[] {
  return report.analysis === 'ac' ? report.frequencies : report.times;
}

export function probeKey(probe: Probe): string {
  if (probe.kind === 'current') return 'I:' + probe.part;
  if (probe.kind === 'node') return 'V:' + probe.pin.part + ':' + probe.pin.terminal;
  return 'ΔV:' + probe.first.part + ':' + probe.first.terminal + '−' + probe.second.part + ':' + probe.second.terminal;
}

function nodeSignal(report: ObservationReport, pin: Pin): Signal | null {
  const node = report.pin_nodes[pin.part + ':' + pin.terminal];
  if (node === undefined) return null;
  if (node === '0') return { key: 'V:0', label: 'Ground', unit: 'V', real: reportAxis(report).map(() => 0),
    ...(report.analysis === 'ac' ? { imaginary: report.frequencies.map(() => 0) } : {}) };
  return namedSignal(report, 'V:' + node);
}

export function namedSignal(report: ObservationReport, name: string): Signal | null {
  if (report.analysis === 'ac') {
    const trace = report.traces.find(trace => trace.name === name);
    return trace ? { key: name, label: name, unit: trace.unit, real: trace.real, imaginary: trace.imaginary } : null;
  }
  const trace = report.traces.find(trace => trace.name === name);
  return trace ? { key: name, label: name, unit: trace.unit, real: trace.values } : null;
}

export function probeSignal(report: ObservationReport, probe: Probe): Signal | null {
  if (probe.kind === 'current') return namedSignal(report, 'I:' + probe.part);
  const first = nodeSignal(report, probe.kind === 'node' ? probe.pin : probe.first);
  if (!first) return null;
  if (probe.kind === 'node') return { ...first, key: probeKey(probe), label: probeKey(probe) };
  const second = nodeSignal(report, probe.second);
  if (!second) return null;
  return { key: probeKey(probe), label: probeKey(probe), unit: 'V',
    real: first.real.map((coefficient, index) => coefficient - second.real[index]),
    ...(first.imaginary && second.imaginary ? { imaginary: first.imaginary.map((coefficient, index) =>
      coefficient - (second.imaginary?.[index] ?? 0)) } : {}) };
}

export function sampleSignal(signal: Signal | null, index: number): ComplexSample | null {
  if (!signal || signal.real[index] === undefined) return null;
  return { real: signal.real[index], imaginary: signal.imaginary?.[index] ?? 0 };
}

export function magnitude(sample: ComplexSample): number { return Math.hypot(sample.real, sample.imaginary); }
export function wrappedPhase(degrees: number): number { return ((degrees + 180) % 360 + 360) % 360 - 180; }
export function relativePhase(sample: ComplexSample, reference: number): number | null {
  if (magnitude(sample) < 1e-12) return null;
  return wrappedPhase(Math.atan2(sample.imaginary, sample.real) * 180 / Math.PI - reference);
}

export function defaultProbes(schematic: Schematic): Probe[] {
  const active = schematic.parts.filter(part => part.kind !== 'GND');
  const voltageParts = [active[0], active.at(-1)].filter(part => part !== undefined);
  return [...voltageParts.map(part => ({ kind: 'differential' as const,
    first: { part: part.id, terminal: 0 as const }, second: { part: part.id, terminal: 1 as const } })),
    ...(active[1] ? [{ kind: 'current' as const, part: active[1].id }] : [])];
}

/** Display reduction retains local minima and maxima; physics/export never use it. */
export function extremaIndices(coefficients: (number | null)[], maximum = 600): number[] {
  if (coefficients.length <= maximum) return coefficients.map((_, index) => index);
  const indices = new Set([0, coefficients.length - 1]);
  const bucket = Math.ceil(coefficients.length / (maximum / 3));
  for (let start = 0; start < coefficients.length; start += bucket) {
    let minimum = start, maximumIndex = start;
    for (let index = start; index < Math.min(start + bucket, coefficients.length); index++) {
      if (coefficients[index] === null) indices.add(index);
      if ((coefficients[index] ?? Infinity) < (coefficients[minimum] ?? Infinity)) minimum = index;
      if ((coefficients[index] ?? -Infinity) > (coefficients[maximumIndex] ?? -Infinity)) maximumIndex = index;
    }
    indices.add(minimum); indices.add(maximumIndex);
  }
  return [...indices].sort((first, second) => first - second);
}

export function unwrapPhases(phases: (number | null)[]): (number | null)[] {
  let previous: number | null = null;
  return phases.map(phase => {
    if (phase === null) { previous = null; return null; }
    const unwrapped = previous === null ? phase : previous + wrappedPhase(phase - previous);
    previous = unwrapped;
    return unwrapped;
  });
}

/** Fixed full-report signed voltage range; never rescales as the time cursor moves. */
export function voltageScale(report: ObservationReport): number {
  if (report.analysis === 'ac') return 0;
  return report.traces.filter(trace => trace.unit === 'V').reduce((limit, trace) =>
    trace.values.reduce((maximum, coefficient) => Math.max(maximum, Math.abs(coefficient)), limit), 0);
}

export function tintedVoltage(voltage: number, limit: number): string {
  const neutral = [216, 181, 146], extreme = voltage < 0 ? [158, 205, 230] : [245, 221, 160];
  const fraction = limit > 0 ? Math.min(1, Math.abs(voltage) / limit) : 0;
  return 'rgb(' + neutral.map((coefficient, index) => Math.round(coefficient + (extreme[index] - coefficient) * fraction)).join(',') + ')';
}
