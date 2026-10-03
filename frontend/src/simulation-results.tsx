import { useState } from 'react';
import { exportReport } from './circuit-api';
import type { Circuit, SimulationReport } from './circuit-types';
import { WaveformChart } from './waveform-chart';

interface Props { circuit: Circuit; report: SimulationReport | null; isStale: boolean }

export function SimulationResults({ circuit, report, isStale }: Props) {
  const [tab, setTab] = useState('waveforms');
  if (!report) return <EmptySimulation />;
  return <section className="results" aria-label="Simulation results">
    <div className="result-header">
      <span className={'status-badge ' + (isStale ? 'stale' : report.status)}>
        {isStale ? 'Parameters changed · rerun required' :
          report.status === 'passed' ? 'Simulation checks passed' : 'Some checks failed'}
      </span>
      <span className="muted">{report.duration_ms.toFixed(0)} ms · ngspice</span>
      <button className="text-button" onClick={() => exportReport(report)}>Export report ↓</button>
    </div>
    <nav className="result-tabs" aria-label="Result views">
      {['waveforms', 'checks', 'connections', 'netlist'].map(view => <button key={view}
        aria-pressed={tab === view} onClick={() => setTab(view)}>{view === 'checks' ? 'Verification checks' : view}</button>)}
    </nav>
    {tab === 'waveforms' && <WaveformChart signals={report.signals} isDc={circuit.id === 'voltage_divider'} />}
    {tab === 'checks' && <div className="checks">
      {report.checks.map(check => <article className={'check ' + (check.passed ? 'pass' : 'fail')} key={check.name}>
        <span aria-hidden="true">{check.passed ? '✓' : '×'}</span>
        <div><h3>{check.name} <small>{check.passed ? 'PASS' : 'FAIL'}</small></h3><p>{check.detail}</p></div>
      </article>)}
    </div>}
    {tab === 'connections' && <div className="connection-view"><h2>Component connectivity</h2>
      <p className="muted">Node 0 is ground. Shared node names represent electrical connections.</p>
      <table><thead><tr><th>Component</th><th>Nodes</th><th>Value / model</th></tr></thead><tbody>
        {circuit.components.map(part => <tr key={part.name}><td>{part.name}</td>
          <td>{part.nodes.join(' ↔ ')}</td><td>{report.parameters[part.name] ?? part.value}</td></tr>)}
      </tbody></table>
    </div>}
    {tab === 'netlist' && <div className="netlist-view"><h2>Simulated netlist</h2><pre>{report.netlist}</pre></div>}
    <div className="report-warning">{report.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>
    <p className="trace-id">Run ID {report.correlation_id}</p>
  </section>;
}

function EmptySimulation() {
  return <section className="empty-state" aria-label="Simulation workspace">
    <svg viewBox="0 0 160 70" aria-hidden="true"><path d="M0 50H20V20H40V50H60V20H80V50H100V20H120V50H160"
      fill="none" stroke="currentColor" strokeWidth="2" /><path d="M0 55Q40 15 160 32"
      fill="none" stroke="#b24d23" strokeWidth="3" /></svg>
    <h2>A circuit is a hypothesis.</h2><p>Run a simulation to see what this one actually does.</p>
    <span className="small-label">REAL NGSPICE · NO GENERATED WAVEFORMS</span>
  </section>;
}
