import { useState } from 'react';
import { PART_NAMES, snapped } from './schematic-model';
import type { PartKind } from './schematic-types';
import type { EditorState } from './use-schematic-editor';

export function AnalogPartsPanel({ editor }: { editor: EditorState }) {
  const [x, setX] = useState(10), [y, setY] = useState(6);
  return <section className="editor-card"><h2>Parts shelf</h2><p className="muted">Choose a part, then click the grid or use the placement controls.</p>
    <div className="parts-shelf">{(Object.keys(PART_NAMES) as PartKind[]).map(kind => <button key={kind}
      disabled={editor.running} aria-pressed={editor.armed === kind} onClick={() => { editor.setArmed(kind); editor.setWireStart(null); }}>
      <span aria-hidden="true">{kind === 'GND' ? '⏚' : kind === 'PULSE' ? '▔▁' : kind}</span>{PART_NAMES[kind]}</button>)}</div>
    <div className="compact-fields"><label>Place column<input type="number" min="2" max="38" value={x} onChange={event => setX(snapped(Number(event.target.value), 38))} /></label>
      <label>Place row<input type="number" min="2" max="22" value={y} onChange={event => setY(snapped(Number(event.target.value), 22))} /></label></div>
    <button className="secondary-action" disabled={!editor.armed || editor.running} onClick={() => editor.place(x, y)}>Add to grid</button>
    <p className="muted">{editor.schematic.parts.length}/20 parts · {editor.schematic.wires.length}/40 wires<br />Analog ideal components · standard values or custom numeric values.</p>
  </section>;
}
