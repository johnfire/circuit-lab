import { translate } from './localization.ts';
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
  return <details className="observation-statistics" open><summary>{translate("observation-statistics-panel.window_statistics")}{engineering(bounds[0], 's')}–{engineering(bounds[1], 's')}</summary>
    {sources.length > 0 && <label>{translate("observation-statistics-panel.phase_reference")}<select aria-label={translate("observation-statistics-panel.phase_reference")} value={reference.id}
      onChange={event => setSelectedReference(event.target.value)}>{sources.map(part => <option key={part.id}>{part.id}</option>)}</select></label>}
    <div role="region" tabIndex={0} aria-label={translate("observation-statistics-panel.scrollable_probe_statistics")} className="measurement-scroll"><table>
      <caption className="sr-only">{translate("observation-statistics-panel.statistics_from_all_samples_in")}</caption>
      <thead><tr><th scope="col">{translate("observation-statistics-panel.probe")}</th><th scope="col">{translate("observation-statistics-panel.mean")}</th><th scope="col">{translate("observation-statistics-panel.total_rms")}</th><th scope="col">{translate("observation-statistics-panel.aconly_rms")}</th><th scope="col">{translate("observation-statistics-panel.peaktopeak")}</th><th scope="col">{translate("observation-statistics-panel.phase_vs")}{reference?.id ?? 'reference'}</th></tr></thead>
      <tbody>{signals.map(signal => {
        const statistics = windowStatistics(report.times, signal.real, bounds);
        const phase = sameFrequency ? settledPhase(report.times, signal.real, frequency, bounds) : null;
        return <tr key={signal.key}><th scope="row">{signal.label}</th>
          {[statistics?.mean, statistics?.rms, statistics?.acRms, statistics?.peakToPeak].map((coefficient, index) =>
            <td key={index}>{coefficient === undefined ? '—' : engineering(coefficient, signal.unit)}</td>)}
          <td>{phase === null || referencePhase === null ? translate("observation-statistics-panel.unavailable") : wrappedPhase(phase - referencePhase).toFixed(1) + '°'}</td></tr>;
      })}</tbody></table></div>
    <p className="muted">{translate("observation-statistics-panel.full_sampled_window_timeweighted_total")}</p>
  </details>;
}
