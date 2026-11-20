import { translate } from './localization.ts';
import type { EditorState } from './use-schematic-editor';

export function AnalogRunControls({ editor }: { editor: EditorState }) {
  const change = (key: 'stop' | 'step', value: number) => editor.commit({ ...editor.schematic,
    timing: { ...editor.schematic.timing, [key]: value / 1000 } }, 'timing.update');
  return <section className="editor-card"><h2>{translate("analog-run-controls.simulation_time")}</h2><fieldset disabled={editor.running}>
    <legend className="sr-only">{translate("analog-run-controls.solver_time_settings")}</legend><div className="compact-fields">
      <label>{translate("analog-run-controls.duration_ms")}<input type="number" min=".001" max="10000" step="any" value={editor.schematic.timing.stop * 1000}
        onChange={event => change('stop', Number(event.target.value))} /></label>
      <label>{translate("analog-run-controls.sample_interval_ms")}<input type="number" min=".0001" max="1000" step="any" value={editor.schematic.timing.step * 1000}
        onChange={event => change('step', Number(event.target.value))} /></label></div>
    <p className="muted">{translate("analog-run-controls.102000_intervals_ngspice_adapts_its")}</p>
    <button className="run-button" onClick={() => { void editor.run(); }}>{editor.running ? translate('common.simulating') : translate("analog-run-controls.simulate_circuit")}<span aria-hidden="true">▶</span></button>
    </fieldset></section>;
}
