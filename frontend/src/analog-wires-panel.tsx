import { pinsFor } from './schematic-model';
import type { EditorState } from './use-schematic-editor';

export function AnalogWiresPanel({ editor }: { editor: EditorState }) {
  const choosePin = (value: string) => { const [part, terminal] = value.split(':'); editor.connect({ part, terminal: terminal === '0' ? 0 : 1 }); };
  return <details className="editor-card"><summary>Connections ({editor.schematic.wires.length})</summary>
    <p className="muted">Use two terminal clicks or this keyboard-friendly terminal selector. No connections are inferred from proximity.</p>
    <label>{editor.wireStart ? 'Connect to terminal' : 'Start wire at terminal'}<select disabled={editor.running} value=""
      onChange={event => { if (event.target.value) choosePin(event.target.value); }}>
      <option value="">Choose terminal…</option>{editor.schematic.parts.flatMap(pinsFor).map(pin => <option key={pin.part + pin.terminal}
        value={pin.part + ':' + pin.terminal}>{pin.part} terminal {pin.terminal}</option>)}</select></label>
    {editor.wireStart && <p>From {editor.wireStart.part}:{editor.wireStart.terminal} <button onClick={() => editor.setWireStart(null)}>Cancel wire</button></p>}
    <ul className="wire-list">{editor.schematic.wires.map((wire, index) => <li key={index}>
      <span>{wire.a.part}:{wire.a.terminal} ↔ {wire.b.part}:{wire.b.terminal}</span>
      <button disabled={editor.running} aria-label={'Remove wire ' + (index + 1)} onClick={() => {
        editor.commit({ ...editor.schematic, wires: editor.schematic.wires.filter((_, previous) => previous !== index) }, 'wire.remove'); editor.setWireStart(null);
      }}>×</button></li>)}</ul>
  </details>;
}
