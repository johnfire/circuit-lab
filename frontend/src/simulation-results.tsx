import { reportText } from './report-localization.ts';
import { translate } from './localization.ts';
import { useState } from 'react';
import { exportReport } from './circuit-api';
import type { Circuit, SimulationReport } from './circuit-types';
import { WaveformChart } from './waveform-chart';

interface Props { circuit: Circuit; report: SimulationReport | null; isStale: boolean }

export function SimulationResults({ circuit, report, isStale }: Props) {
  const [tab, setTab] = useState('waveforms');
  if (!report) return <EmptySimulation />;
  return <section className="results" aria-label={translate("simulation-results.simulation_results")}>
    <div className="result-header">
      <span className={'status-badge ' + (isStale ? 'stale' : report.status)}>
        {isStale ? translate("simulation-results.parameters_changed_rerun_required") :
          report.status === 'passed' ? translate("simulation-results.simulation_checks_passed") : translate("simulation-results.some_checks_failed")}
      </span>
      <span className="muted">{report.duration_ms.toFixed(0)} ms · ngspice</span>
      <button className="text-button" onClick={() => exportReport(report)}>{translate("simulation-results.export_report")}</button>
    </div>
    <nav className="result-tabs" aria-label={translate("simulation-results.result_views")}>
      {['waveforms', 'checks', 'connections', 'netlist'].map(view => <button key={view}
        aria-pressed={tab === view} onClick={() => setTab(view)}>{view === 'checks' ? translate('simulation-results.verification_checks') : translate(view === 'waveforms' ? 'common.waveforms' : view === 'connections' ? 'common.connections' : 'common.netlist')}</button>)}
    </nav>
    {tab === 'waveforms' && <WaveformChart signals={report.signals} isDc={circuit.id === 'voltage_divider'} />}
    {tab === 'checks' && <div className="checks">
      {report.checks.map(check => <article className={'check ' + (check.passed ? 'pass' : 'fail')} key={check.name}>
        <span aria-hidden="true">{check.passed ? '✓' : '×'}</span>
        <div><h3>{reportText(check.name, check.name_message)} <small>{translate(check.passed ? 'common.pass' : 'common.fail')}</small></h3><p>{reportText(check.detail, check.detail_message)}</p></div>
      </article>)}
    </div>}
    {tab === 'connections' && <div className="connection-view"><h2>{translate("simulation-results.component_connectivity")}</h2>
      <p className="muted">{translate("simulation-results.node_0_is_ground_shared")}</p>
      <table><thead><tr><th>{translate("simulation-results.component")}</th><th>{translate("simulation-results.nodes")}</th><th>{translate("simulation-results.value_model")}</th></tr></thead><tbody>
        {circuit.components.map(part => <tr key={part.name}><td>{part.name}</td>
          <td>{part.nodes.join(' ↔ ')}</td><td>{report.parameters[part.name] ?? part.value}</td></tr>)}
      </tbody></table>
    </div>}
    {tab === 'netlist' && <div className="netlist-view"><h2>{translate("simulation-results.simulated_netlist")}</h2><pre>{report.netlist}</pre></div>}
    <div className="report-warning">{report.warnings.map((warning, index) => <p key={warning}>{reportText(warning, report.warning_messages?.[index])}</p>)}</div>
    <p className="trace-id">{translate("simulation-results.run_id")}{report.correlation_id}</p>
  </section>;
}

function EmptySimulation() {
  return <section className="empty-state" aria-label={translate("simulation-results.simulation_workspace")}>
    <svg viewBox="0 0 160 70" aria-hidden="true"><path d="M0 50H20V20H40V50H60V20H80V50H100V20H120V50H160"
      fill="none" stroke="currentColor" strokeWidth="2" /><path d="M0 55Q40 15 160 32"
      fill="none" stroke="#b24d23" strokeWidth="3" /></svg>
    <h2>{translate("simulation-results.a_circuit_is_a_hypothesis")}</h2><p>{translate("simulation-results.run_a_simulation_to_see")}</p>
    <span className="small-label">{translate("simulation-results.real_ngspice_no_generated_waveforms")}</span>
  </section>;
}
