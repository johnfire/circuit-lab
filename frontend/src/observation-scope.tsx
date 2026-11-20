import { translate } from './localization.ts';
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
  return <section className="editor-card observation-scope" aria-label={translate("observation-scope.synchronized_circuit_scope")}><h2>{isAC ? translate("observation-scope.frequency_response") : translate("observation-scope.synchronized_scope")}</h2>
    <p className="muted">{isAC ? translate("observation-scope.shared_frequency_axis_hz_phase")
      : translate("observation-scope.shared_time_axis_seconds_seek")}</p>
    {isAC && <div className="scope-options"><label>{translate("observation-scope.voltage_display")}<select aria-label={translate("observation-scope.voltage_display")} value={metric} onChange={event => setMetric(event.target.value as VoltageMetric)}>
      <option value="amplitude">{translate("observation-scope.amplitude_v_peak")}</option><option value="gain">{translate("observation-scope.gain_vv")}</option><option value="db">{translate("observation-scope.gain_db")}</option></select></label>
      <label className="checkbox-label"><input type="checkbox" checked={unwrapped} onChange={event => setUnwrapped(event.target.checked)} />{translate("observation-scope.unwrap_plotted_phase")}</label></div>}
    <ObservationChart {...shared} title={translate("observation-scope.voltage")} seekLabel={translate("chart.seek_voltage")} unit={isAC && metric !== 'amplitude' ? metric === 'db' ? 'dB' : 'V/V' : 'V'}
      series={series.filter((_, index) => signals[index].unit === 'V')} />
    <ObservationChart {...shared} title={translate("observation-scope.current")} seekLabel={translate("chart.seek_current")} unit="A" series={series.filter((_, index) => signals[index].unit === 'A')} />
    {isAC ? <><ObservationChart {...shared} title={unwrapped ? translate("observation-scope.unwrapped_phase") : translate("observation-scope.phase")} seekLabel={translate(unwrapped ? "chart.seek_unwrapped_phase" : "chart.seek_phase")} unit={translate("common.degrees")} series={phase} phaseWrapped={!unwrapped} />
      <ObservationPhasor report={report} signals={signals} frame={frame} /></>
      : <ObservationStatisticsPanel report={report} schematic={schematic} signals={signals} bounds={bounds} />}
  </section>;
}
