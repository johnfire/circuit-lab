import { useState } from 'react';
import { SchematicPart } from './schematic-part';
import { wirePath } from './schematic-model';
import { gridPoint, useGridDrag } from './use-grid-drag';
import type { EditorState } from './use-schematic-editor';
import type { AnalogReport } from './schematic-types';

export function SchematicCanvas({ editor, report, frame }: { editor: EditorState; report: AnalogReport | null; frame: number }) {
  const [zoom, setZoom] = useState('fit');
  const drag = useGridDrag(part => editor.update(part, false));
  const parts = editor.schematic.parts.map(part => drag.drag?.part.id === part.id ? drag.drag.preview : part);
  return <section className="grid-panel" aria-label="Schematic editor">
    <div className="grid-toolbar"><span>{editor.armed ? 'Click the grid to place ' + editor.armed
      : editor.wireStart ? 'Choose the second terminal · Esc cancels' : 'Drag to move · click two terminals to wire'}</span>
      <label>Zoom <select value={zoom} onChange={event => setZoom(event.target.value)}>
        <option value="fit">Fit</option><option value="100">100%</option><option value="150">150%</option></select></label>
      {(editor.armed || editor.wireStart) && <button onClick={() => { editor.setArmed(null); editor.setWireStart(null); }}>Cancel</button>}
    </div>
    <div className="grid-scroll" tabIndex={0} aria-label="Scrollable circuit grid">
      <svg className={'schematic-grid zoom-' + zoom} viewBox="0 0 1280 768" aria-label="Analog circuit grid"
        onPointerMove={drag.move} onPointerUp={drag.finish} onPointerCancel={drag.cancel}
        onClick={event => { if (event.target === event.currentTarget || (event.target as Element).classList.contains('grid-background')) {
          const point = gridPoint(event); editor.place(point.x, point.y); } }}
        onKeyDown={event => { if (event.key === 'Escape') { editor.setArmed(null); editor.setWireStart(null); drag.cancel(); } }}>
        <defs><pattern id="analog-dots" width="32" height="32" patternUnits="userSpaceOnUse"><circle cx="0" cy="0" r="1.8" /></pattern></defs>
        <rect className="grid-background" width="1280" height="768" fill="url(#analog-dots)" />
        {editor.schematic.wires.map((wire, index) => <path key={index} className="schematic-wire" d={wirePath(wire, parts)} />)}
        {parts.map(part => <SchematicPart key={part.id} part={part} selected={editor.selected === part.id}
          pending={editor.wireStart} disabled={editor.running} report={report} frame={frame}
          onSelect={() => editor.setSelected(part.id)} onConnect={editor.connect} onUpdate={next => editor.update(next, false)}
          onStartDrag={event => { if (!editor.running && !editor.armed && !editor.wireStart) {
            editor.setSelected(part.id); drag.start(part, event); } }} />)}
      </svg>
    </div>
    <p className="grid-footnote">Crossings are not junctions. Only explicit terminal connections conduct. Current signs: terminal 0 → 1.</p>
  </section>;
}
