import { useState } from 'react';
import { simulateAnalog, simulateAC } from './schematic-api';
import type { ACReport, AnalogReport, Schematic, Sweep } from './schematic-types';

export const DEFAULT_SWEEP: Sweep = { source: 'V1', amplitude: 1, phase: 0, start: 1, stop: 1000, spacing: 'log', points: 50 };

/** Keep independent valid reports; failed or electrical edits never leave stale readings. */
export function useAnalogAnalysis(schematic: Schematic, initialError: string) {
  const [report, setReport] = useState<AnalogReport | null>(null);
  const [acReport, setACReport] = useState<ACReport | null>(null);
  const [sweep, setSweep] = useState(DEFAULT_SWEEP);
  const [analysis, setAnalysis] = useState<'transient' | 'ac'>('transient');
  const [error, setError] = useState(initialError);
  const [running, setRunning] = useState(false);
  const [stale, setStale] = useState(false);
  const [failedAnalysis, setFailedAnalysis] = useState<'transient' | 'ac' | null>(null);
  const invalidate = (target: 'transient' | 'ac' | 'both') => {
    setFailedAnalysis(null);
    setStale(Boolean(report || acReport) || stale);
    if (target !== 'ac') setReport(null);
    if (target !== 'transient') setACReport(null);
  };
  const run = async (audit: (action: string, correlation?: string) => void) => {
    if (running) return;
    setRunning(true); setError(''); invalidate(analysis);
    try {
      const completed = analysis === 'ac' ? await simulateAC(schematic, sweep) : await simulateAnalog(schematic);
      if (completed.analysis === 'ac') setACReport(completed); else setReport(completed);
      setStale(false); audit('simulation.' + analysis + '.completed', completed.correlation_id);
    } catch (failure) {
      setFailedAnalysis(analysis);
      setError(failure instanceof Error ? failure.message : 'Simulation unavailable.');
      audit('simulation.' + analysis + '.failed');
    } finally { setRunning(false); }
  };
  return { report, acReport, sweep, analysis, error, running, stale, failedAnalysis, setAnalysis, setError, invalidate, run,
    updateSweep: (next: Sweep) => { setSweep(next); invalidate('ac'); } };
}
