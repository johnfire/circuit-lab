import { reportText } from './report-localization.ts';
import { translate } from './localization.ts';
import { downloadJson } from './schematic-files';
import { probeSignal } from './observation-signals';
import { terminalColumns, terminalReading, voltageReferenceTerminal } from './part-library';
import { signalReading } from './observation-readings';
import type { ACReport, Schematic } from './schematic-types';

export function ACMeasurements({ schematic, report, frame }: { schematic: Schematic; report: ACReport; frame: number }) {
  const columns = terminalColumns(schematic.parts);
  return <details className="editor-card" open><summary>{translate("observation-ac-measurements.measurements_one_shared_frequency")}</summary>
    <div className="measurement-scroll" role="region" tabIndex={0} aria-label={translate("observation-ac-measurements.scrollable_circuit_measurements")}><table>
      <caption className="sr-only">{translate("observation-ac-measurements.peak_magnitude_and_wrapped_phase")}</caption>
      <thead><tr><th scope="col">{translate("observation-ac-measurements.part")}</th>{Array.from({ length: columns }, (_, terminal) => <th key={terminal} scope="col">{translate("observation-ac-measurements.terminal")}{terminal}</th>)}
        <th scope="col">{columns > 2 ? translate("observation-ac-measurements.part_voltage") : 'ΔV 0 − 1'}</th><th scope="col">{columns > 2 ? translate("observation-ac-measurements.current_into_0") : translate("observation-ac-measurements.current_0_1")}</th></tr></thead>
      <tbody>{schematic.parts.filter(part => part.kind !== 'GND').map(part => <tr key={part.id}><th scope="row">{part.id}</th>
        {([0, 1, 2, 3, 4] as const).slice(0, columns).map(terminal => <td key={terminal}>{terminalReading(part, terminal,
          signalReading(report, probeSignal(report, { kind: 'node', pin: { part: part.id, terminal } }), frame))}</td>)}
        <td>{signalReading(report, probeSignal(report, { kind: 'differential', first: { part: part.id, terminal: 0 }, second: { part: part.id, terminal: voltageReferenceTerminal(part.kind) } }), frame)}</td>
        <td>{signalReading(report, probeSignal(report, { kind: 'current', part: part.id }), frame)}</td></tr>)}</tbody></table></div>
    <p className="muted">{translate("observation-ac-measurements.dc_source_biases")}{Object.entries(report.dc_biases).map(([source, bias]) => source + ' = ' + bias + ' V').join('; ')}.</p>
    <button onClick={() => downloadJson('circuit-lab-ac-report.json', report)}>{translate("observation-ac-measurements.export_simulation")}</button>
    <ul className="model-warnings">{report.warnings.map((warning, index) => <li key={warning}>{reportText(warning, report.warning_messages?.[index])}</li>)}</ul>
    <p className="trace-id">{translate("observation-ac-measurements.trace")}{report.correlation_id}</p>
    <details><summary>{translate("observation-ac-measurements.generated_netlist")}</summary><pre className="analog-netlist">{report.netlist}</pre></details>
  </details>;
}
