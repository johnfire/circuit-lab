import { magnitude, relativePhase, sampleSignal, unwrapPhases } from './observation-signals.ts';
import type { Signal } from './observation-signals';
import type { ObservationReport } from './schematic-types';
import type { PlotSeries } from './observation-chart';

export const SCOPE_COLORS = ['#f5dda0', '#9ecde6', '#b4d5ab', '#ecb7c9', '#d5b9f5', '#e7bd91', '#a4ddd5', '#d8b592'];
export type VoltageMetric = 'amplitude' | 'gain' | 'db';

export function scopeSeries(report: ObservationReport, signals: Signal[], metric: VoltageMetric): PlotSeries[] {
  return signals.map((signal, signalIndex) => ({ label: signal.label, color: SCOPE_COLORS[signalIndex % SCOPE_COLORS.length],
    coefficients: signal.real.map((coefficient, index) => {
      if (report.analysis !== 'ac') return coefficient;
      const sample = sampleSignal(signal, index);
      if (!sample) return null;
      const amplitude = magnitude(sample);
      if (signal.unit === 'A' || metric === 'amplitude') return amplitude;
      const gain = amplitude / report.excitation.amplitude;
      return metric === 'db' ? gain > 1e-12 ? 20 * Math.log10(gain) : null : gain;
    }) }));
}

export function phaseSeries(report: ObservationReport, signals: Signal[], unwrapped: boolean): PlotSeries[] {
  if (report.analysis !== 'ac') return [];
  return signals.map((signal, signalIndex) => {
    const phases = signal.real.map((_, index) => {
      const sample = sampleSignal(signal, index);
      return sample ? relativePhase(sample, report.excitation.phase) : null;
    });
    return { label: signal.label, color: SCOPE_COLORS[signalIndex % SCOPE_COLORS.length],
      coefficients: unwrapped ? unwrapPhases(phases) : phases };
  });
}
