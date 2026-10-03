import { CircuitLibrary } from './circuit-library';
import { AccountLinks } from './account-links';
import { ParameterPanel } from './parameter-panel';
import { SimulationResults } from './simulation-results';
import { useCircuitWorkbench } from './use-circuit-workbench';

export function CircuitWorkbench() {
  const state = useCircuitWorkbench();
  const { selected } = state;
  const isHosted = import.meta.env.VITE_DEPLOYMENT_MODE === 'hosted';
  return <div className="workbench">
    <header className="masthead"><a className="brand" href="/"><span className="brand-icon" aria-hidden="true">⌁</span>
      Circuit<span>Lab</span></a><span className="prototype-tag">{isHosted ? 'HOSTED' : 'LOCAL'} PROTOTYPE · 01</span>
      <span className="engine-status"><i />ngspice workbench</span></header>
    {isHosted && <AccountLinks />}
    <CircuitLibrary circuits={state.circuits} selectedId={selected?.id}
      isRunning={state.isRunning} onSelect={state.selectCircuit} />
    <main className="workspace"><div className="workspace-intro">
      <span className="small-label">EXPLORE / {selected?.category.toUpperCase() ?? 'LIBRARY'}</span>
      <h1>{selected?.title ?? 'Loading your workbench…'}</h1><p>{selected?.description}</p>
    </div>
      {state.error && <div className="error-message" role="alert">{state.error}</div>}
      <div role="status" className="run-status">{state.isRunning ? 'Running a real ngspice simulation…' : ''}</div>
      {selected && <div className="workspace-grid">
        <ParameterPanel circuit={selected} values={state.values} rippleLimit={state.rippleLimit} isRunning={state.isRunning}
          onChange={state.changeValue} onRippleChange={state.changeRipple}
          onRun={() => { void state.runSimulation(); }} onReset={() => state.selectCircuit(selected)} />
        <SimulationResults key={selected.id} circuit={selected} report={state.report} isStale={state.isStale} />
      </div>}
    </main><footer className="page-footer">CIRCUIT LAB <span>Think it through. Then test it.</span>
      <span>Generic models · {isHosted ? 'hosted prototype' : 'local only'}</span></footer>
  </div>;
}
