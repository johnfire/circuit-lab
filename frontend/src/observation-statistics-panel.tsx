import { engineering } from './schematic-model';
import { useState } from 'react';
import { probeSignal, wrappedPhase } from './observation-signals';
import { settledPhase, windowStatistics } from './observation-statistics';
import type { Signal } from './observation-signals';
import type { AnalogReport, Schematic } from './schematic-types';

export function ObservationStatisticsPanel({ report, schematic, signals, bounds }: {
  report: AnalogReport; schematic: Schematic; signals: Signal[]; bounds: [number, number];
}) {
  const sources = schematic.parts.filter(part => part.sine);
  const [selectedReference, setSelectedReference] = useState('');
  const reference = sources.find(part => part.id === selectedReference) ?? sources[0], frequency = reference?.sine?.frequency;
  const sameFrequency = frequency !== undefined && sources.every(part => part.sine?.frequency === frequency);
  const referenceSignal = reference ? probeSignal(report, { kind: 'differential', first: { part: reference.id, terminal: 0 }, second: { part: reference.id, terminal: 1 } }) : null;
  const referencePhase = sameFrequency && referenceSignal ? settledPhase(report.times, referenceSignal.real, frequency, bounds) : null;
  return <details className="observation-statistics" open><summary>Window statistics · {engineering(bounds[0], 's')}–{engineering(bounds[1], 's')}</summary>
    {sources.length > 0 && <label>Phase reference<select aria-label="Phase reference" value={reference.id}
      onChange={event => setSelectedReference(event.target.value)}>{sources.map(part => <option key={part.id}>{part.id}</option>)}</select></label>}
    <div role="region" tabIndex={0} aria-label="Scrollable probe statistics" className="measurement-scroll"><table>
      <caption className="sr-only">Statistics from all samples in the selected observation window</caption>
      <thead><tr><th scope="col">Probe</th><th scope="col">Mean</th><th scope="col">Total RMS</th><th scope="col">AC-only RMS</th><th scope="col">Peak-to-peak</th><th scope="col">Phase vs {reference?.id ?? 'reference'}</th></tr></thead>
      <tbody>{signals.map(signal => {
        const statistics = windowStatistics(report.times, signal.real, bounds);
        const phase = sameFrequency ? settledPhase(report.times, signal.real, frequency, bounds) : null;
        return <tr key={signal.key}><th scope="row">{signal.label}</th>
          {[statistics?.mean, statistics?.rms, statistics?.acRms, statistics?.peakToPeak].map((coefficient, index) =>
            <td key={index}>{coefficient === undefined ? '—' : engineering(coefficient, signal.unit)}</td>)}
          <td>{phase === null || referencePhase === null ? 'Unavailable' : wrappedPhase(phase - referencePhase).toFixed(1) + '°'}</td></tr>;
      })}</tbody></table></div>
    <p className="muted">Full sampled window, time-weighted. Total RMS includes DC; AC-only RMS removes the mean. Phase requires ≥3 settled cycles at one sine frequency, ≥40 samples/cycle and a low-residual sine fit; startup or unsuitable windows show unavailable.</p>
  </details>;
}
