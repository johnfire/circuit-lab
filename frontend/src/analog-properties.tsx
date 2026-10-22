import { engineering, PART_NAMES, partValue, rotated, snapped, STANDARD_VALUES } from './schematic-model';
import { isDeviceKind, libraryPart, partsOfKind } from './part-library';
import type { DeviceKind, PinMode } from './schematic-types';
import { BOARDS, boardOf, boardPinOf, MODE_NAMES, pinLabel, placeablePins } from './board-library';
import type { Board, BoardPin } from './board-library';
import { footprintLabel, footprintOptions } from './footprint-options';
import type { Part, Pulse, Sine } from './schematic-types';
import type { EditorState } from './use-schematic-editor';

function DeviceControls({ part, kind, onUpdate }: { part: Part; kind: DeviceKind; onUpdate: (part: Part) => void }) {
  const chosen = libraryPart(part.device);
  return <><label>Library part<select value={part.device ?? ''} onChange={event => onUpdate({ ...part, device: event.target.value })}>
    {partsOfKind(kind).map(option => <option key={option.id} value={option.id}>{option.name} — {option.package}{option.trust === 'draft' ? ' (draft)' : ''}</option>)}
  </select></label>
    {chosen && <><p className="muted">{chosen.description}. Terminals: {chosen.terminals.join(', ')}.</p>
      <p className="muted"><strong>{chosen.trust === 'verified' ? 'Verified' : 'Draft'}</strong>{chosen.trust === 'draft'
        ? ': model and ratings not yet reviewed against the datasheet.' : ': reviewed against its datasheet.'}</p>
      <ul className="model-warnings">{Object.entries(chosen.ratings).map(([name, rating]) =>
        <li key={name}>{name.replace('_max', '')} max {engineering(rating.value, rating.unit)}</li>)}</ul></>}</>;
}

const DEFAULT_PULSE: Pulse = { period: .02, width: .01, delay: .001 };

function withPin(part: Part, board: Board, pin: BoardPin, mode: PinMode): Part {
  return { ...part, board_pin: { board: board.id, pin: pin.id, mode }, pulse: mode === 'pulse' ? part.pulse ?? DEFAULT_PULSE : null };
}

function defaultMode(pin: BoardPin): PinMode {
  return pin.modes.includes('output_high') ? 'output_high' : pin.modes[0];
}

function BoardPinControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const found = boardPinOf(part);
  if (!found || !part.board_pin) return <p className="muted">This board pin is not available.</p>;
  const { board, pin } = found;
  const chooseBoard = (id: string) => { const next = boardOf(id); const first = next && placeablePins(next)[0];
    if (next && first) onUpdate(withPin(part, next, first, defaultMode(first))); };
  const choosePin = (id: string) => { const next = board.pins.find(candidate => candidate.id === id);
    if (next) onUpdate(withPin(part, board, next, next.modes.includes(part.board_pin!.mode) ? part.board_pin!.mode : defaultMode(next))); };
  return <><label>Board<select value={board.id} onChange={event => chooseBoard(event.target.value)}>
      {BOARDS.map(option => <option key={option.id} value={option.id}>{option.name}{option.trust === 'draft' ? ' (draft)' : ''}</option>)}</select></label>
    <label>Header pin<select value={pin.id} onChange={event => choosePin(event.target.value)}>
      {placeablePins(board).map(option => <option key={option.id} value={option.id}>{pinLabel(option)}{option.functions.length ? ' — ' + option.functions.join(', ') : ''}</option>)}</select></label>
    <label>Mode<select value={part.board_pin.mode} onChange={event => onUpdate(withPin(part, board, pin, event.target.value as PinMode))}>
      {pin.modes.map(mode => <option key={mode} value={mode}>{MODE_NAMES[mode]}</option>)}</select></label>
    <p className="muted">{board.logic_voltage} V logic{pin.note ? ' · ' + pin.note : ''} Ground pins: use the Ground symbol; the board's GND is circuit ground.</p>
    {part.pulse && <PulseControls part={part} onUpdate={onUpdate} />}</>;
}

function ValueControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  if (part.kind === 'GND') return <p className="muted">Ground is the 0 V reference. All ground symbols share this reference.</p>;
  if (isDeviceKind(part.kind)) return <DeviceControls part={part} kind={part.kind} onUpdate={onUpdate} />;
  if (part.kind === 'PIN') return <BoardPinControls part={part} onUpdate={onUpdate} />;
  const standards = STANDARD_VALUES[part.kind];
  return <><label>Standard value<select value={part.value} onChange={event => onUpdate({ ...part, value: Number(event.target.value) })}>
    {!standards.includes(part.value) && <option value={part.value}>{partValue(part)} (custom)</option>}
    {standards.map(value => <option key={value} value={value}>{partValue({ ...part, value })}</option>)}</select></label>
    <label>Custom value (SI units)<input type="number" step="any" value={part.value} onChange={event => onUpdate({ ...part, value: Number(event.target.value) })} /></label>
    {part.pulse && <PulseControls part={part} onUpdate={onUpdate} />}
    {part.sine && <SineControls part={part} onUpdate={onUpdate} />}</>;
}

function SineControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const sine = part.sine;
  if (!sine) return null;
  const fields: [keyof Sine, string][] = [['offset', 'DC offset (V)'], ['frequency', 'Sine frequency (Hz)'], ['phase', 'Sine phase (degrees)']];
  return <><p className="muted">Source value is peak amplitude, not RMS. AC sweep excitation is set separately.</p>
    {fields.map(([key, label]) => <label key={key}>{label}<input type="number" step="any" value={sine[key]}
      onChange={event => onUpdate({ ...part, sine: { ...sine, [key]: Number(event.target.value) } })} /></label>)}</>;
}

function PulseControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const pulse = part.pulse;
  if (!pulse) return null;
  const fields: [keyof Pulse, string][] = [['period', 'Pulse period'], ['width', 'High duration'], ['delay', 'Initial delay']];
  return <>{fields.map(([key, label]) => <label key={key}>{label} (ms)<input type="number" min="0" step="any"
    value={Number((pulse[key] * 1000).toPrecision(10))} onChange={event => onUpdate({ ...part, pulse: { ...pulse, [key]: Number(event.target.value) / 1000 } })} /></label>)}</>;
}

function FootprintControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const options = footprintOptions(part);
  if (!options.length) return null;
  const chosen = options.find(option => option.id === part.footprint) ?? options[0];
  return <><label>PCB footprint<select value={chosen.id} onChange={event => onUpdate({ ...part, footprint: event.target.value })}>
    {options.map(option => <option key={option.id} value={option.id}>{footprintLabel(option)}</option>)}</select></label>
    {chosen.note && <p className="muted">{chosen.note}</p>}</>;
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
        <ValueControls part={part} onUpdate={editor.update} /><FootprintControls part={part} onUpdate={next => editor.update(next, false)} />
        <PositionControls part={part} editor={editor} /></fieldset>}
  </section>;
}
