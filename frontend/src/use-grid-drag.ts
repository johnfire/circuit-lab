import { useState } from 'react';
import type { PointerEvent } from 'react';
import { GRID, snapped } from './schematic-model';
import type { Part } from './schematic-types';

export function gridPoint(event: { currentTarget: SVGElement; clientX: number; clientY: number }): { x: number; y: number } {
  const svg = event.currentTarget instanceof SVGSVGElement ? event.currentTarget : event.currentTarget.ownerSVGElement;
  if (!svg) return { x: 2, y: 2 };
  const rectangle = svg.getBoundingClientRect();
  return { x: snapped((event.clientX - rectangle.left) / rectangle.width * 40, 38),
    y: snapped((event.clientY - rectangle.top) / rectangle.height * 24, 22) };
}

export function useGridDrag(onUpdate: (part: Part) => void) {
  const [drag, setDrag] = useState<{ part: Part; offset: { x: number; y: number }; preview: Part } | null>(null);
  const start = (part: Part, event: PointerEvent<SVGGElement>) => {
    event.stopPropagation(); event.preventDefault();
    const point = gridPoint(event);
    event.currentTarget.ownerSVGElement?.setPointerCapture(event.pointerId);
    setDrag({ part, offset: { x: point.x - part.x, y: point.y - part.y }, preview: part });
  };
  const move = (event: PointerEvent<SVGSVGElement>) => {
    if (!drag) return;
    const point = gridPoint(event);
    setDrag({ ...drag, preview: { ...drag.part, x: snapped(point.x - drag.offset.x, 38), y: snapped(point.y - drag.offset.y, 22) } });
  };
  const finish = () => {
    if (drag && (drag.preview.x !== drag.part.x || drag.preview.y !== drag.part.y)) onUpdate(drag.preview);
    setDrag(null);
  };
  return { drag, start, move, finish, cancel: () => setDrag(null), pixels: GRID };
}
