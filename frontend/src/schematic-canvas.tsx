import { useMemo, useState } from 'react';
import { voltageScale } from './observation-signals';
import { SchematicPart } from './schematic-part';
import { wirePath } from './schematic-model';
import { gridPoint, useGridDrag } from './use-grid-drag';
import type { EditorState } from './use-schematic-editor';
import type { ObservationReport } from './schematic-types';
import { NodeReadings, voltageTint } from './observation-grid';
import { nodeLabels, observationViewBox } from './observation-layout';
import type { GridObservation } from './observation-grid';

export function SchematicCanvas({ editor, report, frame, observation }: {
  editor: EditorState; report: ObservationReport | null; frame: number; observation?: GridObservation;
}) {
  const [zoom, setZoom] = useState('fit');
  const voltageLimit = useMemo(() => report ? voltageScale(report) : 0, [report]);
  const drag = useGridDrag(part => editor.update(part, false));
  const parts = editor.schematic.parts.map(part => drag.drag?.part.id === part.id ? drag.drag.preview : part);
  return <section className="grid-panel" aria-label="Schematic editor">
    <div className="grid-toolbar"><span>{editor.armed ? 'Click the grid to place ' + editor.armed
      : observation?.observing ? 'Observe: terminals pin voltage probes; symbols pin branch current. No wiring or dragging.'
        : editor.wireStart ? 'Choose the second terminal · Esc cancels' : 'Drag to move · click two terminals to wire'}</span>
      <label>Zoom <select value={zoom} onChange={event => setZoom(event.target.value)}>
        <option value="fit">Fit</option><option value="100">100%</option><option value="150">150%</option></select></label>
      {(editor.armed || editor.wireStart) && <button onClick={() => { editor.setArmed(null); editor.setWireStart(null); }}>Cancel</button>}
    </div>
    <div className="grid-scroll" tabIndex={0} aria-label="Scrollable circuit grid">
      <svg className={'schematic-grid zoom-' + zoom + (observation?.observing ? ' observing-grid' : '')}
        viewBox={observation?.observing && report ? observationViewBox(parts, nodeLabels(parts, report, editor.schematic.wires)) : '0 0 1280 768'} aria-label="Analog circuit grid"
        onPointerMove={drag.move} onPointerUp={drag.finish} onPointerCancel={drag.cancel}
        onClick={event => { if (event.target === event.currentTarget || (event.target as Element).classList.contains('grid-background')) {
          if (!observation?.observing) { const point = gridPoint(event); editor.place(point.x, point.y); } } }}
        onKeyDown={event => { if (event.key === 'Escape') { editor.setArmed(null); editor.setWireStart(null); drag.cancel(); } }}>
        <defs><pattern id="analog-dots" width="32" height="32" patternUnits="userSpaceOnUse"><circle cx="0" cy="0" r="1.8" /></pattern></defs>
        <rect className="grid-background" width="1280" height="768" fill="url(#analog-dots)" />
        {editor.schematic.wires.map((wire, index) => <path key={index} className="schematic-wire" d={wirePath(wire, parts)}
          style={{ stroke: observation?.shading && report ? voltageTint(report, report.pin_nodes[wire.a.part + ':' + wire.a.terminal], frame, voltageLimit) : undefined }} />)}
        {parts.map(part => <SchematicPart key={part.id} part={part} selected={editor.selected === part.id}
          pending={editor.wireStart} disabled={editor.running} report={report} frame={frame} observation={observation}
          onSelect={() => editor.setSelected(part.id)} onConnect={editor.connect} onUpdate={next => editor.update(next, false)}
          onStartDrag={event => { if (!observation?.observing && !editor.running && !editor.armed && !editor.wireStart) {
            editor.setSelected(part.id); drag.start(part, event); } }} />)}
        {observation?.observing && report && <NodeReadings parts={parts} wires={editor.schematic.wires} report={report} frame={frame} />}
      </svg>
    </div>
    <p className="grid-footnote">Crossings are not junctions. Only explicit terminal connections conduct. Current signs: terminal 0 → 1.</p>
  </section>;
}
