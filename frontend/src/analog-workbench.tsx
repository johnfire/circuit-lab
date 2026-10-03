import { AnalogFileControls } from './analog-file-controls';
import { AnalogMeasurements } from './analog-measurements';
import { AnalogPartsPanel } from './analog-parts-panel';
import { AnalogProperties } from './analog-properties';
import { AnalogRunControls } from './analog-run-controls';
import { AnalogTimeline } from './analog-timeline';
import { AnalogWiresPanel } from './analog-wires-panel';
import { SchematicCanvas } from './schematic-canvas';
import { useAnalogPlayback } from './use-analog-playback';
import { useSchematicEditor } from './use-schematic-editor';
import { useDraftScope } from './use-draft-scope';
import type { EditorState } from './use-schematic-editor';
import type { AnalogReport } from './schematic-types';
import './schematic.css';

function AnalogSession({ editor, report }: { editor: EditorState; report: AnalogReport }) {
  const playback = useAnalogPlayback(report);
  return <><SchematicCanvas editor={editor} report={report} frame={playback.index} />
    <AnalogTimeline playback={playback} report={report} />
    <AnalogMeasurements schematic={editor.schematic} report={report} frame={playback.index} /></>;
}

function ScopedAnalogWorkbench({ scope }: { scope: string | null }) {
  const editor = useSchematicEditor(scope);
  return <main className="analog-workbench"><div className="analog-intro"><span className="small-label">BUILD / ANALOG</span>
    <h1>Your circuit, one instant at a time.</h1><p>Place standard components. Connect their terminals. See what actually happens.</p>
    <AnalogFileControls editor={editor} /></div>
    {editor.error && <div className="error-message" role="alert">{editor.error}</div>}
    <div className="run-status" role="status">{editor.running ? 'Running real ngspice in the isolated worker…'
      : editor.report ? 'Simulation complete. Scrub or play to inspect the circuit.' : 'Ready to edit. Simulate to show voltages and currents.'}</div>
    <div className="analog-layout"><aside className="analog-sidebar" aria-label="Circuit building controls">
      <AnalogPartsPanel editor={editor} /><AnalogProperties editor={editor} />
      <AnalogRunControls editor={editor} /><AnalogWiresPanel editor={editor} /></aside>
      <div className="analog-board">{editor.report ? <AnalogSession key={editor.report.correlation_id} editor={editor} report={editor.report} />
        : <><SchematicCanvas editor={editor} report={null} frame={0} /><section className="editor-card ready-note">
          <h2>Start with the RC charging example</h2><p>The pulse source switches from 0 to 5 V after 1 ms. Watch C1 charge through R1, then discharge when the pulse falls.</p>
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
