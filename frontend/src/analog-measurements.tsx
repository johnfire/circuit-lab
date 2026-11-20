import { reportText } from './report-localization.ts';
import { translate } from './localization.ts';
import { engineering } from './schematic-model';
import { terminalColumns, terminalReading } from './part-library';
import { downloadJson } from './schematic-files';
import type { AnalogReport, Schematic } from './schematic-types';

export function AnalogMeasurements({ schematic, report, frame }: { schematic: Schematic; report: AnalogReport; frame: number }) {
  const voltage = (id: string, terminal: number) => {
    const node = report.pin_nodes[id + ':' + terminal];
    const value = node === '0' ? 0 : report.traces.find(trace => trace.name === 'V:' + node)?.values[frame];
    return value === undefined ? '—' : engineering(value, 'V');
  };
  const columns = terminalColumns(schematic.parts);
  return <details className="editor-card" open><summary>{translate("analog-measurements.measurements_one_shared_instant")}</summary>
    <div className="measurement-scroll" role="region" tabIndex={0} aria-label={translate("analog-measurements.scrollable_circuit_measurements")}><table><caption className="sr-only">{translate("analog-measurements.synchronized_terminal_voltages_and_signed")}</caption>
      <thead><tr><th scope="col">{translate("analog-measurements.part")}</th>{Array.from({ length: columns }, (_, terminal) => <th key={terminal} scope="col">{translate("analog-measurements.terminal")}{terminal}</th>)}
        <th scope="col">{columns > 2 ? translate("analog-measurements.current_into_0") : translate("analog-measurements.current_0_1")}</th></tr></thead>
      <tbody>{schematic.parts.filter(part => part.kind !== 'GND').map(part => {
        const current = report.traces.find(trace => trace.name === 'I:' + part.id)?.values[frame];
        return <tr key={part.id}><th scope="row">{part.id}</th>{Array.from({ length: columns }, (_, terminal) =>
          <td key={terminal}>{terminalReading(part, terminal, voltage(part.id, terminal))}</td>)}
          <td>{current === undefined ? '—' : engineering(current, 'A')}</td></tr>;
      })}</tbody></table></div>
    <p className="muted">{columns > 2 ? translate("analog-measurements.conventional_current_is_signed_into")
      : translate("analog-measurements.conventional_current_is_signed_terminal")}{translate("analog-measurements.energy_delivery_depends_on_v")}</p>
    <button onClick={() => downloadJson('circuit-lab-analog-report.json', report)}>{translate("analog-measurements.export_simulation")}</button>
    <ul className="model-warnings">{report.warnings.map((warning, index) => <li key={warning}>{reportText(warning, report.warning_messages?.[index])}</li>)}</ul>
    <p className="trace-id">{translate("analog-measurements.trace")}{report.correlation_id}</p>
    <details><summary>{translate("analog-measurements.generated_netlist")}</summary><pre className="analog-netlist">{report.netlist}</pre></details>
  </details>;
}
