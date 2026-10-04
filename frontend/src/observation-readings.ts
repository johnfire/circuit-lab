import { engineering } from './schematic-model.ts';
import { magnitude, relativePhase, sampleSignal } from './observation-signals.ts';
import type { Signal } from './observation-signals';
import type { ObservationReport } from './schematic-types';

export function signalReading(report: ObservationReport, signal: Signal | null, index: number): string {
  const sample = sampleSignal(signal, index);
  if (!sample || !signal) return '—';
  if (report.analysis !== 'ac') return engineering(sample.real, signal.unit);
  const phase = relativePhase(sample, report.excitation.phase);
  return engineering(magnitude(sample), signal.unit) + ' ∠ ' + (phase === null ? '—' : phase.toFixed(1) + '°');
}
