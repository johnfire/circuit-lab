import { downloadJson } from './schematic-files';
import { probeSignal } from './observation-signals';
import { signalReading } from './observation-readings';
import type { ACReport, Schematic } from './schematic-types';

export function ACMeasurements({ schematic, report, frame }: { schematic: Schematic; report: ACReport; frame: number }) {
  return <details className="editor-card" open><summary>Measurements · one shared frequency</summary>
    <div className="measurement-scroll" role="region" tabIndex={0} aria-label="Scrollable circuit measurements"><table>
      <caption className="sr-only">Peak magnitude and wrapped phase relative to excitation</caption>
      <thead><tr><th scope="col">Part</th><th scope="col">Terminal 0</th><th scope="col">Terminal 1</th><th scope="col">ΔV 0 − 1</th><th scope="col">Current 0 → 1</th></tr></thead>
      <tbody>{schematic.parts.filter(part => part.kind !== 'GND').map(part => <tr key={part.id}><th scope="row">{part.id}</th>
        {[0, 1].map(terminal => <td key={terminal}>{signalReading(report, probeSignal(report, { kind: 'node', pin: { part: part.id, terminal: terminal as 0 | 1 } }), frame)}</td>)}
        <td>{signalReading(report, probeSignal(report, { kind: 'differential', first: { part: part.id, terminal: 0 }, second: { part: part.id, terminal: 1 } }), frame)}</td>
        <td>{signalReading(report, probeSignal(report, { kind: 'current', part: part.id }), frame)}</td></tr>)}</tbody></table></div>
    <p className="muted">DC source biases: {Object.entries(report.dc_biases).map(([source, bias]) => source + ' = ' + bias + ' V').join('; ')}.</p>
    <button onClick={() => downloadJson('circuit-lab-ac-report.json', report)}>Export simulation</button>
    <ul className="model-warnings">{report.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>
    <p className="trace-id">Trace: {report.correlation_id}</p>
    <details><summary>Generated netlist</summary><pre className="analog-netlist">{report.netlist}</pre></details>
  </details>;
}
