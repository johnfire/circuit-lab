import { useState } from 'react';
import { ObservationChart } from './observation-chart';
import { probeSignal, reportAxis } from './observation-signals';
import { phaseSeries, scopeSeries } from './observation-scope-series';
import { ObservationStatisticsPanel } from './observation-statistics-panel';
import { ObservationPhasor } from './observation-phasor';
import type { VoltageMetric } from './observation-scope-series';
import type { ObservationReport, Probe, Schematic } from './schematic-types';

export function ObservationScope({ report, schematic, probes, frame, bounds, onSeek }: {
  report: ObservationReport; schematic: Schematic; probes: Probe[]; frame: number;
  bounds: [number, number]; onSeek: (index: number) => void;
}) {
  const [metric, setMetric] = useState<VoltageMetric>('amplitude');
  const [unwrapped, setUnwrapped] = useState(false);
  const signals = probes.map(probe => probeSignal(report, probe)).filter(signal => signal !== null);
  const series = scopeSeries(report, signals, metric), phase = phaseSeries(report, signals, unwrapped);
  const axis = reportAxis(report), isAC = report.analysis === 'ac';
  const shared = { axis, index: frame, bounds, logarithmic: isAC && report.excitation.spacing === 'log', onSeek };
  return <section className="editor-card observation-scope" aria-label="Synchronized circuit scope"><h2>{isAC ? 'Frequency response' : 'Synchronized scope'}</h2>
    <p className="muted">{isAC ? 'Shared frequency axis (Hz). Phase is relative to excitation; amplitudes are peak magnitudes.'
      : 'Shared time axis (seconds). Seek either plot to update every grid reading.'}</p>
    {isAC && <div className="scope-options"><label>Voltage display<select aria-label="Voltage display" value={metric} onChange={event => setMetric(event.target.value as VoltageMetric)}>
      <option value="amplitude">Amplitude (V peak)</option><option value="gain">Gain (V/V)</option><option value="db">Gain (dB)</option></select></label>
      <label className="checkbox-label"><input type="checkbox" checked={unwrapped} onChange={event => setUnwrapped(event.target.checked)} />Unwrap plotted phase</label></div>}
    <ObservationChart {...shared} title="Voltage" unit={isAC && metric !== 'amplitude' ? metric === 'db' ? 'dB' : 'V/V' : 'V'}
      series={series.filter((_, index) => signals[index].unit === 'V')} />
    <ObservationChart {...shared} title="Current" unit="A" series={series.filter((_, index) => signals[index].unit === 'A')} />
    {isAC ? <><ObservationChart {...shared} title={unwrapped ? 'Unwrapped phase' : 'Phase'} unit="degrees" series={phase} phaseWrapped={!unwrapped} />
      <ObservationPhasor report={report} signals={signals} frame={frame} /></>
      : <ObservationStatisticsPanel report={report} schematic={schematic} signals={signals} bounds={bounds} />}
  </section>;
}
