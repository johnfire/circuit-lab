import { GRID, pinPosition, pinsFor } from './schematic-model.ts';
import type { ObservationReport, Part, Pin, Wire } from './schematic-types';

export interface LabelBox { x: number; y: number; width: number; height: number }
export interface NodeLabel { node: string; pin: Pin; anchor: { x: number; y: number }; box: LabelBox }

export function overlaps(first: LabelBox, second: LabelBox): boolean {
  return first.x < second.x + second.width && first.x + first.width > second.x &&
    first.y < second.y + second.height && first.y + first.height > second.y;
}

export function wireBoxes(parts: Part[], wires: Wire[]): LabelBox[] {
  return wires.flatMap(wire => {
    const first = parts.find(part => part.id === wire.a.part), second = parts.find(part => part.id === wire.b.part);
    if (!first || !second) return [];
    const start = pinPosition(first, wire.a.terminal), end = pinPosition(second, wire.b.terminal);
    const middle = Math.round((start.x + end.x) / (2 * GRID)) * GRID;
    const points = [start, { x: middle, y: start.y }, { x: middle, y: end.y }, end];
    return points.slice(1).map((point, index) => ({ x: Math.min(point.x, points[index].x) - 8,
      y: Math.min(point.y, points[index].y) - 8, width: Math.abs(point.x - points[index].x) + 16,
      height: Math.abs(point.y - points[index].y) + 16 }));
  });
}

/** One node label per net, avoiding symbols, annotations and orthogonal wire segments. */
export function nodeLabels(parts: Part[], report: ObservationReport, wires: Wire[]): NodeLabel[] {
  const occupied = [...wireBoxes(parts, wires), ...parts.flatMap(part =>
    [{ x: part.x * GRID - 70, y: part.y * GRID - 70, width: 140, height: 140 },
      { x: part.x * GRID + 45, y: part.y * GRID - 45, width: 300, height: 118 }])];
  const seen = new Set<string>(), labels: NodeLabel[] = [];
  for (const part of parts) for (const pin of pinsFor(part)) {
    const node = report.pin_nodes[pin.part + ':' + pin.terminal];
    if (!node || seen.has(node)) continue;
    seen.add(node);
    const anchor = pinPosition(part, pin.terminal);
    let box = { x: anchor.x + 15, y: anchor.y - 60, width: 230, height: 32 };
    for (let attempt = 0; attempt < 120 && occupied.some(existing => overlaps(box, existing)); attempt++) {
      const ring = Math.floor(attempt / 4) + 1;
      const offsets = [[24, -64 - ring * 36], [-250, -64 - ring * 36], [24, 64 + ring * 36], [-250, 64 + ring * 36]];
      const offset = offsets[attempt % 4];
      box = { ...box, x: anchor.x + offset[0], y: anchor.y + offset[1] };
    }
    occupied.push(box); labels.push({ node, pin, anchor, box });
  }
  return labels;
}

export function observationViewBox(parts: Part[], labels: NodeLabel[]): string {
  const boxes = [...parts.map(part => ({ x: part.x * GRID - 110, y: part.y * GRID - 100, width: 440, height: 210 })),
    ...labels.map(label => label.box)];
  if (!boxes.length) return '0 0 1280 768';
  const left = Math.min(...boxes.map(box => box.x)) - 24, top = Math.min(...boxes.map(box => box.y)) - 24;
  const right = Math.max(...boxes.map(box => box.x + box.width)) + 24;
  const bottom = Math.max(...boxes.map(box => box.y + box.height)) + 24;
  return [left, top, right - left, bottom - top].join(' ');
}
