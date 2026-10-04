import { AnalogFileControls } from './analog-file-controls';
import { useState } from 'react';
import { AnalogPartsPanel } from './analog-parts-panel';
import { AnalogProperties } from './analog-properties';
import { AnalogRunControls } from './analog-run-controls';
import { AnalogSweepControls } from './analog-sweep-controls';
import { AnalogObservationSession } from './analog-observation-session';
import { ObservationToolbar } from './observation-toolbar';
import { AnalogWiresPanel } from './analog-wires-panel';
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
  return <main className="analog-workbench"><div className="analog-intro"><span className="small-label">BUILD / ANALOG</span>
    <h1>Your circuit, one instant at a time.</h1><p>Place standard components. Connect their terminals. See what actually happens.</p>
    <AnalogFileControls editor={editor} /></div>
    {editor.error && <div className="error-message" role="alert">{editor.error}</div>}
    <div className="run-status" role="status">{editor.running ? 'Running real ngspice in the isolated worker…'
      : editor.failedAnalysis === editor.analysis ? 'Simulation failed. No current readings are displayed; correct the reported problem and run again.'
        : report ? editor.analysis === 'ac' ? 'Frequency sweep complete. Choose a frequency to inspect amplitude and phase; this is not time playback.'
          : 'Simulation complete. Paused for inspection. Zero readings at time zero may be the initial DC state; move the cursor to watch the response.'
        : editor.stale ? 'Readings stale after electrical or analysis edits. Run again; old readings are hidden.' : 'Not simulated. Run to show voltages and currents.'}</div>
    <div className={'analog-layout ' + (observing ? 'observation-layout' : '')}><aside hidden={observing} className="analog-sidebar" aria-label="Circuit building controls">
      <AnalogPartsPanel editor={editor} /><AnalogProperties editor={editor} />
      {editor.analysis === 'ac' ? <AnalogSweepControls editor={editor} /> : <AnalogRunControls editor={editor} />}<AnalogWiresPanel editor={editor} /></aside>
      <div className="analog-board">{report ? <AnalogObservationSession key={report.correlation_id} editor={editor} report={report} controls={controls} />
        : <><ObservationToolbar editor={editor} controls={controls} /><SchematicCanvas editor={editor} report={null} frame={0} /><section className="editor-card ready-note">
          <h2>{editor.analysis === 'ac' ? 'Choose your AC excitation' : 'Ready to observe your circuit'}</h2>
          <p>{editor.analysis === 'ac' ? 'Set sweep settings in Build mode. Frequency analysis uses separate AC excitation and preserves DC source biases.'
            : 'The initial RC example charges then discharges. Try an AC example to watch a sine wave, current reversal and phase relationships.'}</p>
          <p>Change R1 or C1, simulate again, and compare. Electrical edits clear old readings.</p></section></>}
      </div></div>
    <p className="muted">Prototype: browser-only drafts and file exports. Ideal analog simulation is not a hardware safety check.</p>
  </main>;
}

export function AnalogWorkbench() {
  const session = useDraftScope();
  if (!session.ready) return <main className="analog-workbench"><p role="status">Opening your circuit workspace…</p></main>;
  return <ScopedAnalogWorkbench key={session.scope ?? 'memory-only'} scope={session.scope} />;
}
