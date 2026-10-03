import { PART_NAMES, partValue, rotated, snapped, STANDARD_VALUES } from './schematic-model';
import type { Part, Pulse } from './schematic-types';
import type { EditorState } from './use-schematic-editor';

function ValueControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  if (part.kind === 'GND') return <p className="muted">Ground is the 0 V reference. All ground symbols share this reference.</p>;
  const standards = STANDARD_VALUES[part.kind];
  return <><label>Standard value<select value={part.value} onChange={event => onUpdate({ ...part, value: Number(event.target.value) })}>
    {!standards.includes(part.value) && <option value={part.value}>{partValue(part)} (custom)</option>}
    {standards.map(value => <option key={value} value={value}>{partValue({ ...part, value })}</option>)}</select></label>
    <label>Custom value (SI units)<input type="number" step="any" value={part.value} onChange={event => onUpdate({ ...part, value: Number(event.target.value) })} /></label>
    {part.pulse && <PulseControls part={part} onUpdate={onUpdate} />}</>;
}

function PulseControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const pulse = part.pulse;
  if (!pulse) return null;
  const fields: [keyof Pulse, string][] = [['period', 'Pulse period'], ['width', 'High duration'], ['delay', 'Initial delay']];
  return <>{fields.map(([key, label]) => <label key={key}>{label} (ms)<input type="number" min="0" step="any"
    value={Number((pulse[key] * 1000).toPrecision(10))} onChange={event => onUpdate({ ...part, pulse: { ...pulse, [key]: Number(event.target.value) / 1000 } })} /></label>)}</>;
}

function PositionControls({ part, editor }: { part: Part; editor: EditorState }) {
  const move = (x: number, y: number) => editor.update({ ...part, x: snapped(x, 38), y: snapped(y, 22) }, false);
  return <><div className="compact-fields">
    <label>Column<input type="number" min="2" max="38" value={part.x} onChange={event => move(Number(event.target.value), part.y)} /></label>
    <label>Row<input type="number" min="2" max="22" value={part.y} onChange={event => move(part.x, Number(event.target.value))} /></label></div>
    <div className="move-controls"><button onClick={() => move(part.x - 1, part.y)} aria-label="Move left">←</button>
      <button onClick={() => move(part.x, part.y - 1)} aria-label="Move up">↑</button>
      <button onClick={() => move(part.x, part.y + 1)} aria-label="Move down">↓</button>
      <button onClick={() => move(part.x + 1, part.y)} aria-label="Move right">→</button></div>
    <div className="button-row"><button onClick={() => editor.update({ ...part, rotation: rotated(part.rotation) }, false)}>Rotate 90°</button>
      <button onClick={() => editor.remove(part.id)}>Remove part</button></div>
    <p className="muted">Rotation: {part.rotation}° · Moving and rotating preserve terminal connections.</p></>;
}

export function AnalogProperties({ editor }: { editor: EditorState }) {
  const part = editor.schematic.parts.find(part => part.id === editor.selected);
  return <section className="editor-card"><h2>{part ? part.id + ' · ' + PART_NAMES[part.kind] : 'Component properties'}</h2>
    {!part ? <p className="muted">Select a symbol to change its value, orientation or placement.</p>
      : <fieldset disabled={editor.running}><legend className="sr-only">Edit {part.id}</legend>
        <ValueControls part={part} onUpdate={editor.update} /><PositionControls part={part} editor={editor} /></fieldset>}
  </section>;
}
