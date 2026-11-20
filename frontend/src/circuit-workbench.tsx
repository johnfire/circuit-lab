import { displayMessage } from './display-message.ts';
import { translate } from './localization.ts';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LanguageSelector } from './language-selector';
import { AnalogWorkbench } from './analog-workbench';
import { WorkbenchBoundary } from './workbench-boundary';
import { CircuitLibrary } from './circuit-library';
import { AccountLinks } from './account-links';
import { ParameterPanel } from './parameter-panel';
import { SimulationResults } from './simulation-results';
import { useCircuitWorkbench } from './use-circuit-workbench';

export function CircuitWorkbench() {
  useTranslation();
  const [building, setBuilding] = useState(new URLSearchParams(window.location.search).get('mode') === 'build');
  const state = useCircuitWorkbench();
  const { selected } = state;
  const isHosted = import.meta.env.VITE_DEPLOYMENT_MODE === 'hosted';
  return <div className="workbench">
    <header className="masthead"><a className="brand" href="/"><span className="brand-icon" aria-hidden="true">⌁</span>
      Circuit<span>Lab</span></a><span className="prototype-tag">{isHosted ? translate('common.hosted') : translate('common.local')} {translate("circuit-workbench.prototype_01")}</span>
      <span className="engine-status"><i />{translate("circuit-workbench.ngspice_workbench")}</span><LanguageSelector hosted={isHosted} /></header>
    {isHosted && <AccountLinks />}
    <nav className="workbench-modes" aria-label={translate("circuit-workbench.workbench_mode")}><button aria-pressed={!building} onClick={() => setBuilding(false)}>{translate("circuit-workbench.examples")}</button>
      <button aria-pressed={building} onClick={() => setBuilding(true)}>{translate("circuit-workbench.build_circuit")}</button></nav>
    {building ? <WorkbenchBoundary><AnalogWorkbench /></WorkbenchBoundary> : <><CircuitLibrary circuits={state.circuits} selectedId={selected?.id}
      isRunning={state.isRunning} onSelect={state.selectCircuit} />
    <main className="workspace"><div className="workspace-intro">
      <span className="small-label">{translate("circuit-workbench.explore")}{selected ? translate(selected.category === 'digital' ? 'common.digital' : 'common.analogue').toUpperCase() : translate('common.library').toUpperCase()}</span>
      <h1>{selected?.title ?? translate("circuit-workbench.loading_your_workbench")}</h1><p>{selected?.description}</p>
    </div>
      {state.error && <div className="error-message" role="alert">{displayMessage(state.error)}</div>}
      <div role="status" className="run-status">{state.isRunning ? translate("circuit-workbench.running_a_real_ngspice_simulation") : ''}</div>
      {selected && <div className="workspace-grid">
        <ParameterPanel circuit={selected} values={state.values} rippleLimit={state.rippleLimit} isRunning={state.isRunning}
          onChange={state.changeValue} onRippleChange={state.changeRipple}
          onRun={() => { void state.runSimulation(); }} onReset={() => state.selectCircuit(selected)} />
        <SimulationResults key={selected.id} circuit={selected} report={state.report} isStale={state.isStale} />
      </div>}
    </main></>}<footer className="page-footer">CIRCUIT LAB <span>{translate("circuit-workbench.think_it_through_then_test")}</span>
      <span>{translate("circuit-workbench.generic_models")}{isHosted ? translate("circuit-workbench.hosted_prototype") : translate("circuit-workbench.local_only")}</span></footer>
  </div>;
}
