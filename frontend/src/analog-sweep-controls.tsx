import type { EditorState } from './use-schematic-editor';
import type { Sweep } from './schematic-types';

export function AnalogSweepControls({ editor }: { editor: EditorState }) {
  const sweep = editor.sweep;
  const update = (key: keyof Sweep, coefficient: string | number) => editor.updateSweep({ ...sweep, [key]: coefficient });
  const fields: [keyof Sweep, string][] = [['amplitude', 'AC amplitude (V peak)'], ['phase', 'AC phase (degrees)'],
    ['start', 'Sweep start (Hz)'], ['stop', 'Sweep end (Hz)'], ['points', sweep.spacing === 'log' ? 'Points per decade' : 'Frequency points']];
  return <section className="editor-card"><h2>Frequency sweep</h2><fieldset disabled={editor.running}>
    <legend className="sr-only">Small-signal AC settings</legend>
    <label>AC excitation source<select value={sweep.source} onChange={event => update('source', event.target.value)}>
      {editor.schematic.parts.filter(part => ['V', 'PULSE', 'SIN'].includes(part.kind)).map(part => <option key={part.id}>{part.id}</option>)}</select></label>
    <label>Sweep spacing<select value={sweep.spacing} onChange={event => update('spacing', event.target.value)}>
      <option value="log">Logarithmic</option><option value="linear">Linear</option></select></label>
    {fields.map(([key, label]) => <label key={key}>{label}<input type="number" step="any" value={sweep[key]}
      onChange={event => update(key, Number(event.target.value))} /></label>)}
    <p className="muted">1 mHz–1 MHz; 2–1000 total frequency points. Log density is requested points/decade; ngspice aligns both endpoints. DC biases remain; other sources have AC 0. Sine peak and frequency do not control this sweep.</p>
    <button className="run-button" onClick={() => { void editor.run(); }}>{editor.running ? 'Simulating…' : 'Run frequency sweep'}</button>
  </fieldset></section>;
}
