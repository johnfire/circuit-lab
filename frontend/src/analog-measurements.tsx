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
  return <details className="editor-card" open><summary>Measurements · one shared instant</summary>
    <div className="measurement-scroll" role="region" tabIndex={0} aria-label="Scrollable circuit measurements"><table><caption className="sr-only">Synchronized terminal voltages and signed branch currents</caption>
      <thead><tr><th scope="col">Part</th>{Array.from({ length: columns }, (_, terminal) => <th key={terminal} scope="col">Terminal {terminal}</th>)}
        <th scope="col">{columns > 2 ? 'Current into 0' : 'Current 0 → 1'}</th></tr></thead>
      <tbody>{schematic.parts.filter(part => part.kind !== 'GND').map(part => {
        const current = report.traces.find(trace => trace.name === 'I:' + part.id)?.values[frame];
        return <tr key={part.id}><th scope="row">{part.id}</th>{Array.from({ length: columns }, (_, terminal) =>
          <td key={terminal}>{terminalReading(part, terminal, voltage(part.id, terminal))}</td>)}
          <td>{current === undefined ? '—' : engineering(current, 'A')}</td></tr>;
      })}</tbody></table></div>
    <p className="muted">{columns > 2 ? 'Conventional current is signed into terminal 0: 0 → 1 for two-terminal parts; into the drain, collector or output for multi-terminal devices.'
      : 'Conventional current is signed terminal 0 → 1.'} Energy delivery depends on ΔV × I, not the current sign alone.</p>
    <button onClick={() => downloadJson('circuit-lab-analog-report.json', report)}>Export simulation</button>
    <ul className="model-warnings">{report.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>
    <p className="trace-id">Trace: {report.correlation_id}</p>
    <details><summary>Generated netlist</summary><pre className="analog-netlist">{report.netlist}</pre></details>
  </details>;
}
