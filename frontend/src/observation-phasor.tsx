import { translate } from './localization.ts';
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
  return <details className="phasor-panel"><summary>{translate("observation-phasor.selectedprobe_phasor")}</summary>
    <label>{translate("observation-phasor.phasor_probe")}<select value={signal?.key ?? ''} onChange={event => setSelected(event.target.value)}>
      {signals.map(signal => <option key={signal.key} value={signal.key}>{signal.label}</option>)}</select></label>
    <svg viewBox="0 0 240 210" role="img" aria-label={translate("observation-phasor.normalized_phasor") + (signal?.label ?? translate('observation-phasor.unavailable'))}>
      <circle cx="120" cy="100" r="75" className="scope-gridline" /><path className="scope-gridline" d="M25 100 H210 M120 10 V190" />
      <path className="phasor-reference" d="M120 100 H195" />
      {phase !== null && <path className="scope-cursor" d={'M120 100 L' + (120 + 75 * Math.cos(angle)) + ' ' + (100 - 75 * Math.sin(angle))} />}
      <text x="140" y="92">{translate("observation-phasor.reference_0")}</text>
    </svg><p>{sample && signal ? engineering(magnitude(sample), signal.unit) : '—'} ∠ {phase === null ? translate("observation-phasor.unavailable") : phase.toFixed(1) + '°'}</p>
    <p className="muted">{translate("observation-phasor.normalized_vector_length_not_a")}</p>
  </details>;
}
