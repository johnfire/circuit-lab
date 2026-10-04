import { useState } from 'react';
import { magnitude, relativePhase, sampleSignal } from './observation-signals';
import { engineering } from './schematic-model';
import type { Signal } from './observation-signals';
import type { ACReport } from './schematic-types';

export function ObservationPhasor({ report, signals, frame }: { report: ACReport; signals: Signal[]; frame: number }) {
  const [selected, setSelected] = useState('');
  const signal = signals.find(signal => signal.key === selected) ?? signals[0];
  const sample = sampleSignal(signal ?? null, frame);
  const phase = sample ? relativePhase(sample, report.excitation.phase) : null;
  const angle = (phase ?? 0) * Math.PI / 180;
  return <details className="phasor-panel"><summary>Selected-probe phasor</summary>
    <label>Phasor probe<select value={signal?.key ?? ''} onChange={event => setSelected(event.target.value)}>
      {signals.map(signal => <option key={signal.key} value={signal.key}>{signal.label}</option>)}</select></label>
    <svg viewBox="0 0 240 210" role="img" aria-label={'Normalized phasor ' + (signal?.label ?? 'unavailable')}>
      <circle cx="120" cy="100" r="75" className="scope-gridline" /><path className="scope-gridline" d="M25 100 H210 M120 10 V190" />
      <path className="phasor-reference" d="M120 100 H195" />
      {phase !== null && <path className="scope-cursor" d={'M120 100 L' + (120 + 75 * Math.cos(angle)) + ' ' + (100 - 75 * Math.sin(angle))} />}
      <text x="140" y="92">reference 0°</text>
    </svg><p>{sample && signal ? engineering(magnitude(sample), signal.unit) : '—'} ∠ {phase === null ? 'Unavailable' : phase.toFixed(1) + '°'}</p>
    <p className="muted">Normalized vector length, not a shared V/A scale. Direction is phase relative to AC excitation, not time playback.</p>
  </details>;
}
