import { translate } from './localization.ts';
import type { EditorState } from './use-schematic-editor';
import type { Sweep } from './schematic-types';

export function AnalogSweepControls({ editor }: { editor: EditorState }) {
  const sweep = editor.sweep;
  const update = (key: keyof Sweep, coefficient: string | number) => editor.updateSweep({ ...sweep, [key]: coefficient });
  const fields: [keyof Sweep, string][] = [['amplitude', translate("analog-sweep-controls.ac_amplitude_v_peak")], ['phase', translate("analog-sweep-controls.ac_phase_degrees")],
    ['start', translate("analog-sweep-controls.sweep_start_hz")], ['stop', translate("analog-sweep-controls.sweep_end_hz")], ['points', sweep.spacing === 'log' ? translate("analog-sweep-controls.points_per_decade") : translate("analog-sweep-controls.frequency_points")]];
  return <section className="editor-card"><h2>{translate("analog-sweep-controls.frequency_sweep")}</h2><fieldset disabled={editor.running}>
    <legend className="sr-only">{translate("analog-sweep-controls.smallsignal_ac_settings")}</legend>
    <label>{translate("analog-sweep-controls.ac_excitation_source")}<select value={sweep.source} onChange={event => update('source', event.target.value)}>
      {editor.schematic.parts.filter(part => ['V', 'PULSE', 'SIN'].includes(part.kind)).map(part => <option key={part.id}>{part.id}</option>)}</select></label>
    <label>{translate("analog-sweep-controls.sweep_spacing")}<select value={sweep.spacing} onChange={event => update('spacing', event.target.value)}>
      <option value="log">{translate("analog-sweep-controls.logarithmic")}</option><option value="linear">{translate("analog-sweep-controls.linear")}</option></select></label>
    {fields.map(([key, label]) => <label key={key}>{label}<input type="number" step="any" value={sweep[key]}
      onChange={event => update(key, Number(event.target.value))} /></label>)}
    <p className="muted">{translate("analog-sweep-controls.1_mhz1_mhz_21000_total")}</p>
    <button className="run-button" onClick={() => { void editor.run(); }}>{editor.running ? translate('common.simulating') : translate("analog-sweep-controls.run_frequency_sweep")}</button>
  </fieldset></section>;
}
