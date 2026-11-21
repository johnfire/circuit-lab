import { displayMessage } from './display-message.ts';
import { translate } from './localization.ts';
import { AnalogFileControls } from './analog-file-controls';
import { AnalogProjectControls } from './analog-project-controls';
import { useState } from 'react';
import { AnalogPartsPanel } from './analog-parts-panel';
import { BlockLibraryPanel } from './block-library-panel';
import { AnalogProperties } from './analog-properties';
import { AnalogRunControls } from './analog-run-controls';
import { AnalogSweepControls } from './analog-sweep-controls';
import { AnalogObservationSession } from './analog-observation-session';
import { ObservationToolbar } from './observation-toolbar';
import { AnalogWiresPanel } from './analog-wires-panel';
import { BoardPinout } from './board-pinout';
import { PcbReview } from './pcb-review';
import { PcbExport } from './pcb-export';
import { SchematicCanvas } from './schematic-canvas';
import { useSchematicEditor } from './use-schematic-editor';
import { useDraftScope } from './use-draft-scope';
import './schematic.css';
import './observation.css';

function ScopedAnalogWorkbench({ scope }: { scope: string | null }) {
  const editor = useSchematicEditor(scope);
  const [observing, setObserving] = useState(false);
  const report = editor.analysis === 'ac' ? editor.acReport : editor.report;
  const controls = { observing, setObserving };
  return <main className="analog-workbench"><div className="analog-intro"><span className="small-label">{translate("analog-workbench.build_analog")}</span>
    <h1>{translate("analog-workbench.your_circuit_one_instant_at")}</h1><p>{translate("analog-workbench.place_standard_components_connect_their")}</p>
    <AnalogFileControls editor={editor} /></div><AnalogProjectControls editor={editor} />
    {editor.error && <div className="error-message" role="alert">{displayMessage(editor.error)}</div>}
    <div className="run-status" role="status">{editor.running ? translate("analog-workbench.running_real_ngspice_in_the")
      : editor.failedAnalysis === editor.analysis ? translate("analog-workbench.simulation_failed_no_current_readings")
        : report ? editor.analysis === 'ac' ? translate("analog-workbench.frequency_sweep_complete_choose_a")
          : translate("analog-workbench.simulation_complete_paused_for_inspection")
        : editor.stale ? translate("analog-workbench.readings_stale_after_electrical_or") : translate("analog-workbench.not_simulated_run_to_show")}</div>
    <div className={'analog-layout ' + (observing ? 'observation-layout' : '')}><aside hidden={observing} className="analog-sidebar" aria-label={translate("analog-workbench.circuit_building_controls")}>
      <AnalogPartsPanel editor={editor} /><BlockLibraryPanel editor={editor} /><AnalogProperties editor={editor} />
      {editor.analysis === 'ac' ? <AnalogSweepControls editor={editor} /> : <AnalogRunControls editor={editor} />}<AnalogWiresPanel editor={editor} /><BoardPinout schematic={editor.schematic} /><PcbExport editor={editor} /></aside>
      <div className="analog-board">{report ? <AnalogObservationSession key={report.correlation_id} editor={editor} report={report} controls={controls} />
        : <><ObservationToolbar editor={editor} controls={controls} /><SchematicCanvas editor={editor} report={null} frame={0} /><section className="editor-card ready-note">
          <h2>{editor.analysis === 'ac' ? translate("analog-workbench.choose_your_ac_excitation") : translate("analog-workbench.ready_to_observe_your_circuit")}</h2>
          <p>{editor.analysis === 'ac' ? translate("analog-workbench.set_sweep_settings_in_build")
            : translate("analog-workbench.the_initial_rc_example_charges")}</p>
          <p>{translate("analog-workbench.change_r1_or_c1_simulate")}</p></section></>}
      </div></div>
    <PcbReview circuit={editor.schematic} />
    <p className="muted">{translate("analog-workbench.local_drafts_stay_in_this")}</p>
  </main>;
}

export function AnalogWorkbench() {
  const session = useDraftScope();
  if (!session.ready) return <main className="analog-workbench"><p role="status">{translate("analog-workbench.opening_your_circuit_workspace")}</p></main>;
  return <ScopedAnalogWorkbench key={session.scope ?? 'memory-only'} scope={session.scope} />;
}
