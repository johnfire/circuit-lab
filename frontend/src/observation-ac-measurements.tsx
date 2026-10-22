import { downloadJson } from './schematic-files';
import { probeSignal } from './observation-signals';
import { terminalColumns, terminalReading, voltageReferenceTerminal } from './part-library';
import { signalReading } from './observation-readings';
import type { ACReport, Schematic } from './schematic-types';

export function ACMeasurements({ schematic, report, frame }: { schematic: Schematic; report: ACReport; frame: number }) {
  const columns = terminalColumns(schematic.parts);
  return <details className="editor-card" open><summary>Measurements · one shared frequency</summary>
    <div className="measurement-scroll" role="region" tabIndex={0} aria-label="Scrollable circuit measurements"><table>
      <caption className="sr-only">Peak magnitude and wrapped phase relative to excitation</caption>
      <thead><tr><th scope="col">Part</th>{Array.from({ length: columns }, (_, terminal) => <th key={terminal} scope="col">Terminal {terminal}</th>)}
        <th scope="col">{columns === 3 ? 'Part voltage' : 'ΔV 0 − 1'}</th><th scope="col">{columns === 3 ? 'Current into 0' : 'Current 0 → 1'}</th></tr></thead>
      <tbody>{schematic.parts.filter(part => part.kind !== 'GND').map(part => <tr key={part.id}><th scope="row">{part.id}</th>
        {([0, 1, 2] as const).slice(0, columns).map(terminal => <td key={terminal}>{terminalReading(part, terminal,
          signalReading(report, probeSignal(report, { kind: 'node', pin: { part: part.id, terminal } }), frame))}</td>)}
        <td>{signalReading(report, probeSignal(report, { kind: 'differential', first: { part: part.id, terminal: 0 }, second: { part: part.id, terminal: voltageReferenceTerminal(part.kind) } }), frame)}</td>
        <td>{signalReading(report, probeSignal(report, { kind: 'current', part: part.id }), frame)}</td></tr>)}</tbody></table></div>
    <p className="muted">DC source biases: {Object.entries(report.dc_biases).map(([source, bias]) => source + ' = ' + bias + ' V').join('; ')}.</p>
    <button onClick={() => downloadJson('circuit-lab-ac-report.json', report)}>Export simulation</button>
    <ul className="model-warnings">{report.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>
    <p className="trace-id">Trace: {report.correlation_id}</p>
    <details><summary>Generated netlist</summary><pre className="analog-netlist">{report.netlist}</pre></details>
  </details>;
}
