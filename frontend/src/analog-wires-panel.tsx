import { translate } from './localization.ts';
import { pinsFor } from './schematic-model';
import { terminalName } from './part-library';
import type { Terminal } from './schematic-types';
import type { EditorState } from './use-schematic-editor';

export function AnalogWiresPanel({ editor }: { editor: EditorState }) {
  const choosePin = (value: string) => { const [part, terminal] = value.split(':'); editor.connect({ part, terminal: Number(terminal) as Terminal }); };
  const label = (part: string, terminal: number) => { const found = editor.schematic.parts.find(candidate => candidate.id === part);
    return part + ' ' + (found ? terminalName(found, terminal) : String(terminal)); };
  return <details className="editor-card"><summary>{translate("analog-wires-panel.connections")}{editor.schematic.wires.length})</summary>
    <p className="muted">{translate("analog-wires-panel.use_two_terminal_clicks_or")}</p>
    <label>{editor.wireStart ? translate("analog-wires-panel.connect_to_terminal") : translate("analog-wires-panel.start_wire_at_terminal")}<select disabled={editor.running} value=""
      onChange={event => { if (event.target.value) choosePin(event.target.value); }}>
      <option value="">{translate("analog-wires-panel.choose_terminal")}</option>{editor.schematic.parts.flatMap(pinsFor).map(pin => <option key={pin.part + pin.terminal}
        value={pin.part + ':' + pin.terminal}>{label(pin.part, pin.terminal)}</option>)}</select></label>
    {editor.wireStart && <p>{translate("analog-wires-panel.from")}{label(editor.wireStart.part, editor.wireStart.terminal)} <button onClick={() => editor.setWireStart(null)}>{translate("analog-wires-panel.cancel_wire")}</button></p>}
    <ul className="wire-list">{editor.schematic.wires.map((wire, index) => <li key={index}>
      <span>{label(wire.a.part, wire.a.terminal)} ↔ {label(wire.b.part, wire.b.terminal)}</span>
      <button disabled={editor.running} aria-label={translate("analog-wires-panel.remove_wire") + (index + 1)} onClick={() => {
        editor.commit({ ...editor.schematic, wires: editor.schematic.wires.filter((_, previous) => previous !== index) }, 'wire.remove'); editor.setWireStart(null);
      }}>×</button></li>)}</ul>
  </details>;
}
