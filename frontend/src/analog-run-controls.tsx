import type { EditorState } from './use-schematic-editor';

export function AnalogRunControls({ editor }: { editor: EditorState }) {
  const change = (key: 'stop' | 'step', value: number) => editor.commit({ ...editor.schematic,
    timing: { ...editor.schematic.timing, [key]: value / 1000 } }, 'timing.update');
  return <section className="editor-card"><h2>Simulation time</h2><fieldset disabled={editor.running}>
    <legend className="sr-only">Solver time settings</legend><div className="compact-fields">
      <label>Duration (ms)<input type="number" min=".001" max="10000" step="any" value={editor.schematic.timing.stop * 1000}
        onChange={event => change('stop', Number(event.target.value))} /></label>
      <label>Sample interval (ms)<input type="number" min=".0001" max="1000" step="any" value={editor.schematic.timing.step * 1000}
        onChange={event => change('step', Number(event.target.value))} /></label></div>
    <p className="muted">10–2000 intervals. ngspice adapts its internal steps; displayed frames share this uniform interval.</p>
    <button className="run-button" onClick={() => { void editor.run(); }}>{editor.running ? 'Simulating…' : 'Simulate circuit'}<span aria-hidden="true">▶</span></button>
    </fieldset></section>;
}
