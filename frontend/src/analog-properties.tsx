import { RATING_LABELS } from './rating-labels.ts';
import { translate } from './localization.ts';
import { engineering, PART_NAMES, partValue, rotated, snapped, STANDARD_VALUES } from './schematic-model';
import { isDeviceKind, libraryPart, partsOfKind } from './part-library';
import type { DeviceKind, PinMode } from './schematic-types';
import { BOARDS, boardOf, boardPinOf, MODE_NAMES, pinLabel, placeablePins } from './board-library';
import type { Board, BoardPin } from './board-library';
import { footprintLabel, footprintOptions } from './footprint-options';
import type { FootprintOption } from './footprint-options';
import type { Part, Pulse, Sine } from './schematic-types';
import type { EditorState } from './use-schematic-editor';

function DeviceControls({ part, kind, onUpdate }: { part: Part; kind: DeviceKind; onUpdate: (part: Part) => void }) {
  const chosen = libraryPart(part.device);
  return <><label>{translate("analog-properties.library_part")}<select value={part.device ?? ''} onChange={event => onUpdate({ ...part, device: event.target.value })}>
    {partsOfKind(kind).map(option => <option key={option.id} value={option.id}>{option.name} — {option.package}{option.trust === 'draft' ? translate("analog-properties.draft") : ''}</option>)}
  </select></label>
    {chosen && <><p className="muted">{chosen.description}{translate("analog-properties.terminals")}{chosen.terminals.join(', ')}.</p>
      <p className="muted"><strong>{chosen.trust === 'verified' ? translate("analog-properties.verified") : translate("analog-properties.draft_2")}</strong>{chosen.trust === 'draft'
        ? translate("analog-properties.model_and_ratings_not_yet") : translate("analog-properties.reviewed_against_its_datasheet")}</p>
      <ul className="model-warnings">{Object.entries(chosen.ratings).map(([name, rating]) =>
        <li key={name}>{RATING_LABELS[name] ?? name}{translate("analog-properties.max")}{engineering(rating.value, rating.unit)}</li>)}</ul></>}</>;
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
  if (!found || !part.board_pin) return <p className="muted">{translate("analog-properties.this_board_pin_is_not")}</p>;
  const { board, pin } = found;
  const chooseBoard = (id: string) => { const next = boardOf(id); const first = next && placeablePins(next)[0];
    if (next && first) onUpdate(withPin(part, next, first, defaultMode(first))); };
  const choosePin = (id: string) => { const next = board.pins.find(candidate => candidate.id === id);
    if (next) onUpdate(withPin(part, board, next, next.modes.includes(part.board_pin!.mode) ? part.board_pin!.mode : defaultMode(next))); };
  return <><label>{translate("analog-properties.board")}<select value={board.id} onChange={event => chooseBoard(event.target.value)}>
      {BOARDS.map(option => <option key={option.id} value={option.id}>{option.name}{option.trust === 'draft' ? translate("analog-properties.draft") : ''}</option>)}</select></label>
    <label>{translate("analog-properties.header_pin")}<select value={pin.id} onChange={event => choosePin(event.target.value)}>
      {placeablePins(board).map(option => <option key={option.id} value={option.id}>{pinLabel(option)}{option.functions.length ? ' — ' + option.functions.join(', ') : ''}</option>)}</select></label>
    <label>{translate("analog-properties.mode")}<select value={part.board_pin.mode} onChange={event => onUpdate(withPin(part, board, pin, event.target.value as PinMode))}>
      {pin.modes.map(mode => <option key={mode} value={mode}>{MODE_NAMES[mode]}</option>)}</select></label>
    <p className="muted">{board.logic_voltage}{translate("analog-properties.v_logic")}{pin.note ? ' · ' + pin.note : ''}{translate("analog-properties.ground_pins_use_the_ground")}</p>
    {part.pulse && <PulseControls part={part} onUpdate={onUpdate} />}</>;
}

function ValueControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  if (part.kind === 'GND') return <p className="muted">{translate("analog-properties.ground_is_the_0_v")}</p>;
  if (isDeviceKind(part.kind)) return <DeviceControls part={part} kind={part.kind} onUpdate={onUpdate} />;
  if (part.kind === 'PIN') return <BoardPinControls part={part} onUpdate={onUpdate} />;
  const standards = STANDARD_VALUES[part.kind];
  return <><label>{translate("analog-properties.standard_value")}<select value={part.value} onChange={event => onUpdate({ ...part, value: Number(event.target.value) })}>
    {!standards.includes(part.value) && <option value={part.value}>{partValue(part)}{translate("analog-properties.custom")}</option>}
    {standards.map(value => <option key={value} value={value}>{partValue({ ...part, value })}</option>)}</select></label>
    <label>{translate("analog-properties.custom_value_si_units")}<input type="number" step="any" value={part.value} onChange={event => onUpdate({ ...part, value: Number(event.target.value) })} /></label>
    {part.pulse && <PulseControls part={part} onUpdate={onUpdate} />}
    {part.sine && <SineControls part={part} onUpdate={onUpdate} />}</>;
}

function SineControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const sine = part.sine;
  if (!sine) return null;
  const fields: [keyof Sine, string][] = [['offset', translate("analog-properties.dc_offset_v")], ['frequency', translate("analog-properties.sine_frequency_hz")], ['phase', translate("analog-properties.sine_phase_degrees")]];
  return <><p className="muted">{translate("analog-properties.source_value_is_peak_amplitude")}</p>
    {fields.map(([key, label]) => <label key={key}>{label}<input type="number" step="any" value={sine[key]}
      onChange={event => onUpdate({ ...part, sine: { ...sine, [key]: Number(event.target.value) } })} /></label>)}</>;
}

function PulseControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const pulse = part.pulse;
  if (!pulse) return null;
  const fields: [keyof Pulse, string][] = [['period', translate("analog-properties.pulse_period")], ['width', translate("analog-properties.high_duration")], ['delay', translate("analog-properties.initial_delay")]];
  return <>{fields.map(([key, label]) => <label key={key}>{label} (ms)<input type="number" min="0" step="any"
    value={Number((pulse[key] * 1000).toPrecision(10))} onChange={event => onUpdate({ ...part, pulse: { ...pulse, [key]: Number(event.target.value) / 1000 } })} /></label>)}</>;
}

function FootprintControls({ part, onUpdate }: { part: Part; onUpdate: (part: Part) => void }) {
  const options = footprintOptions(part);
  if (!options.length) return null;
  const chosen = options.find(option => option.id === part.footprint) ?? options[0];
  return <><label>{translate("analog-properties.pcb_footprint")}<select value={chosen.id} onChange={event => onUpdate({ ...part, footprint: event.target.value })}>
    {options.map(option => <option key={option.id} value={option.id}>{footprintLabel(option)}</option>)}</select></label>
    {chosen.note && <p className="muted">{chosen.note}</p>}
    <PassiveRatingControls part={part} option={chosen} onUpdate={onUpdate} /></>;
}

function PassiveRatingControls({ part, option, onUpdate }: { part: Part; option: FootprintOption; onUpdate: (part: Part) => void }) {
  const ratings = option.ratings ?? {};
  if (part.kind === 'R') return <p className="muted">{translate("analog-properties.checked_against_this_package")}{engineering(ratings.power_max?.value ?? 0, 'W')}{translate("analog-properties.and")}{' '}
    {engineering(ratings.voltage_max?.value ?? 0, 'V')}{translate("analog-properties.max_2")}{ratings.power_max?.source ?? translate("analog-properties.no_source")}).</p>;
  if (part.kind !== 'C') return null;
  return <><label>{translate("analog-properties.voltage_rating_v")}<input type="number" min="1" max="1000" step="any" placeholder={translate("analog-properties.not_set_simulate_for_a")}
    value={part.voltage_rating ?? ''} onChange={event => onUpdate({ ...part, voltage_rating: event.target.value === '' ? null : Number(event.target.value) })} /></label>
    <p className="muted">{part.voltage_rating ? translate("analog-properties.every_run_checks_the_voltage") : translate("analog-properties.not_checked_until_you_set")}
      {option.dielectric === 'electrolytic' && translate("analog-properties.electrolytic_terminal_0_is_and")}</p></>;
}

function PositionControls({ part, editor }: { part: Part; editor: EditorState }) {
  const move = (x: number, y: number) => editor.update({ ...part, x: snapped(x, 38), y: snapped(y, 22) }, false);
  return <><div className="compact-fields">
    <label>{translate("analog-properties.column")}<input type="number" min="2" max="38" value={part.x} onChange={event => move(Number(event.target.value), part.y)} /></label>
    <label>{translate("analog-properties.row")}<input type="number" min="2" max="22" value={part.y} onChange={event => move(part.x, Number(event.target.value))} /></label></div>
    <div className="move-controls"><button onClick={() => move(part.x - 1, part.y)} aria-label={translate("analog-properties.move_left")}>←</button>
      <button onClick={() => move(part.x, part.y - 1)} aria-label={translate("analog-properties.move_up")}>↑</button>
      <button onClick={() => move(part.x, part.y + 1)} aria-label={translate("analog-properties.move_down")}>↓</button>
      <button onClick={() => move(part.x + 1, part.y)} aria-label={translate("analog-properties.move_right")}>→</button></div>
    <div className="button-row"><button onClick={() => editor.update({ ...part, rotation: rotated(part.rotation) }, false)}>{translate("analog-properties.rotate_90")}</button>
      <button onClick={() => editor.remove(part.id)}>{translate("analog-properties.remove_part")}</button></div>
    <p className="muted">{translate("analog-properties.rotation")}{part.rotation}{translate("analog-properties.moving_and_rotating_preserve_terminal")}</p></>;
}

export function AnalogProperties({ editor }: { editor: EditorState }) {
  const part = editor.schematic.parts.find(part => part.id === editor.selected);
  return <section className="editor-card"><h2>{part ? part.id + ' · ' + PART_NAMES[part.kind] : translate("analog-properties.component_properties")}</h2>
    {!part ? <p className="muted">{translate("analog-properties.select_a_symbol_to_change")}</p>
      : <fieldset disabled={editor.running}><legend className="sr-only">{translate("analog-properties.edit")}{part.id}</legend>
        <ValueControls part={part} onUpdate={editor.update} /><FootprintControls part={part} onUpdate={next => editor.update(next, false)} />
        <PositionControls part={part} editor={editor} /></fieldset>}
  </section>;
}
