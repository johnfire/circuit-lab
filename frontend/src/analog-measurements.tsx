import { engineering } from './schematic-model';
import { downloadJson } from './schematic-files';
import type { AnalogReport, Schematic } from './schematic-types';

export function AnalogMeasurements({ schematic, report, frame }: { schematic: Schematic; report: AnalogReport; frame: number }) {
  const voltage = (id: string, terminal: number) => {
    const node = report.pin_nodes[id + ':' + terminal];
    const value = node === '0' ? 0 : report.traces.find(trace => trace.name === 'V:' + node)?.values[frame];
    return value === undefined ? '—' : engineering(value, 'V');
  };
  return <details className="editor-card" open><summary>Measurements · one shared instant</summary>
    <div className="measurement-scroll"><table><caption className="sr-only">Synchronized terminal voltages and signed branch currents</caption>
      <thead><tr><th scope="col">Part</th><th scope="col">Terminal 0</th><th scope="col">Terminal 1</th><th scope="col">Current 0 → 1</th></tr></thead>
      <tbody>{schematic.parts.filter(part => part.kind !== 'GND').map(part => {
        const current = report.traces.find(trace => trace.name === 'I:' + part.id)?.values[frame];
        return <tr key={part.id}><th scope="row">{part.id}</th><td>{voltage(part.id, 0)}</td><td>{voltage(part.id, 1)}</td>
          <td>{current === undefined ? '—' : engineering(current, 'A')}</td></tr>;
      })}</tbody></table></div>
    <p className="muted">A negative source current means it is supplying energy in this terminal orientation.</p>
    <button onClick={() => downloadJson('circuit-lab-analog-report.json', report)}>Export simulation</button>
    <ul className="model-warnings">{report.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>
    <p className="trace-id">Trace: {report.correlation_id}</p>
    <details><summary>Generated netlist</summary><pre className="analog-netlist">{report.netlist}</pre></details>
  </details>;
}
