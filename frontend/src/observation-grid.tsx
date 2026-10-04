import { engineering, GRID } from './schematic-model';
import { namedSignal, probeSignal, sampleSignal, tintedVoltage } from './observation-signals';
import { signalReading } from './observation-readings';
import type { ObservationReport, Part, Pin, Wire } from './schematic-types';
import { nodeLabels } from './observation-layout';

export interface GridObservation {
  observing: boolean; markers: boolean; playing: boolean; shading: boolean;
  onPin: (pin: Pin) => void; onCurrent: (part: string) => void;
}

export function NodeReadings({ parts, wires, report, frame }: { parts: Part[]; wires: Wire[]; report: ObservationReport; frame: number }) {
  return <g className="observation-node-labels">{nodeLabels(parts, report, wires).map(label => <g key={label.node}>
    <path className="reading-leader" d={'M' + label.anchor.x + ' ' + label.anchor.y + ' L' + label.box.x + ' ' + (label.box.y + 16)} />
    <rect className="reading-background" x={label.box.x} y={label.box.y} width={label.box.width} height={label.box.height} rx="5" />
    <text className="node-reading" x={label.box.x + 8} y={label.box.y + 22}>{label.node} · {signalReading(report,
      probeSignal(report, { kind: 'node', pin: label.pin }), frame)}</text>
  </g>)}</g>;
}

export function BranchDirection({ part, report, frame, observation }: {
  part: Part; report: ObservationReport; frame: number; observation: GridObservation;
}) {
  if (report.analysis === 'ac' || part.kind === 'GND') return null;
  const current = sampleSignal(namedSignal(report, 'I:' + part.id), frame)?.real;
  if (current === undefined || Math.abs(current) < 1e-12) return null;
  const direction = current < 0 ? '1 → 0' : '0 → 1';
  const duration = Math.max(.4, Math.min(3, 1 / (1 + Math.abs(current) * 1000)));
  return <g className="branch-direction" role="img" aria-label={part.id + ' current ' + engineering(current, 'A') + ', direction ' + direction}
    data-direction={direction} transform={'translate(' + part.x * GRID + ' ' + part.y * GRID + ') rotate(' + part.rotation + ')'}>
    <g transform={current < 0 ? 'rotate(180)' : undefined}><path d="M-34 34 H34 M24 26 L34 34 L24 42" />
      {observation.markers && observation.playing && <circle className="flow-marker" r="3" cy="34"
        style={{ animationDuration: duration + 's' }} />}</g>
  </g>;
}

export function voltageTint(report: ObservationReport, node: string | undefined, frame: number, limit: number): string | undefined {
  if (report.analysis === 'ac' || !node || node === '0') return undefined;
  const voltage = namedSignal(report, 'V:' + node)?.real[frame];
  if (voltage === undefined) return undefined;
  return tintedVoltage(voltage, limit);
}
