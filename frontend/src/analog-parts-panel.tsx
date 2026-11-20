import { translate } from './localization.ts';
import { useState } from 'react';
import { PART_NAMES, snapped } from './schematic-model';
import type { PartKind } from './schematic-types';
import type { EditorState } from './use-schematic-editor';

const SHELF_ICONS: Partial<Record<PartKind, string>> = { GND: '⏚', PULSE: '▔▁', D: '▷|', NMOS: 'N', PMOS: 'P', NPN: 'Q', PNP: 'Q', OPAMP: '▷', REG: 'REG', PIN: 'IO' };

export function AnalogPartsPanel({ editor }: { editor: EditorState }) {
  const [x, setX] = useState(10), [y, setY] = useState(6);
  return <section className="editor-card"><h2>{translate("analog-parts-panel.parts_shelf")}</h2><p className="muted">{translate("analog-parts-panel.choose_a_part_then_click")}</p>
    <div className="parts-shelf">{(Object.keys(PART_NAMES) as PartKind[]).map(kind => <button key={kind}
      disabled={editor.running} aria-pressed={editor.armed === kind} onClick={() => { editor.setArmed(kind); editor.setWireStart(null); }}>
      <span aria-hidden="true">{SHELF_ICONS[kind] ?? kind}</span>{PART_NAMES[kind]}</button>)}</div>
    <div className="compact-fields"><label>{translate("analog-parts-panel.place_column")}<input type="number" min="2" max="38" value={x} onChange={event => setX(snapped(Number(event.target.value), 38))} /></label>
      <label>{translate("analog-parts-panel.place_row")}<input type="number" min="2" max="22" value={y} onChange={event => setY(snapped(Number(event.target.value), 22))} /></label></div>
    <button className="secondary-action" disabled={!editor.armed || editor.running} onClick={() => editor.place(x, y)}>{translate("analog-parts-panel.add_to_grid")}</button>
    <p className="muted">{translate('parts.count', { parts: editor.schematic.parts.length, wires: editor.schematic.wires.length })}<br />{translate("analog-parts-panel.rcl_and_sources_plus_library")}</p>
  </section>;
}
