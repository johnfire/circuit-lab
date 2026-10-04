import type { KeyboardEvent, PointerEvent } from 'react';
import { engineering, GRID, partValue, pinKey, pinPosition, pinsFor, snapped } from './schematic-model';
import { SchematicSymbol } from './schematic-symbol';
import type { ObservationReport, Part, Pin } from './schematic-types';
import { namedSignal, probeSignal } from './observation-signals';
import { signalReading } from './observation-readings';
import { BranchDirection } from './observation-grid';
import type { GridObservation } from './observation-grid';

interface PartProps {
  part: Part; selected: boolean; pending: Pin | null; report: ObservationReport | null; frame: number; disabled: boolean;
  observation?: GridObservation;
  onSelect: () => void; onStartDrag: (event: PointerEvent<SVGGElement>) => void;
  onUpdate: (part: Part) => void; onConnect: (pin: Pin) => void;
}

function partKey(event: KeyboardEvent<SVGGElement>, props: PartProps) {
  if (props.disabled) return;
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); props.onSelect(); }
  const shifts: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  const shift = shifts[event.key];
  if (shift && !props.observation?.observing) { event.preventDefault(); props.onUpdate({ ...props.part,
    x: snapped(props.part.x + shift[0], 38), y: snapped(props.part.y + shift[1], 22) }); }
}

function Terminal({ pin, props }: { pin: Pin; props: PartProps }) {
  const position = pinPosition(props.part, pin.terminal);
  const node = props.report?.pin_nodes[pinKey(pin)];
  const trace = props.report && props.report.analysis !== 'ac' ? props.report.traces.find(trace => trace.name === 'V:' + node) : null;
  const value = node === '0' ? 0 : trace?.values[props.frame];
  const pending = props.pending && pinKey(props.pending) === pinKey(pin);
  const activate = () => { if (!props.disabled) {
    if (props.observation?.observing) props.observation.onPin(pin); else props.onConnect(pin);
  } };
  return <g>
    <circle className={'terminal ' + (pending ? 'pending' : '')} cx={position.x} cy={position.y} r="9"
      role="button" tabIndex={props.disabled ? -1 : 0} aria-label={props.part.id + ' terminal ' + pin.terminal}
      aria-pressed={Boolean(pending)} onClick={event => { event.stopPropagation(); activate(); }}
      onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); } }} />
    <text className="terminal-label" aria-hidden="true" x={position.x + 12} y={position.y + 18}>{pin.terminal}</text>
    {value !== undefined && !props.observation?.observing && <text className="node-reading" x={position.x + 12} y={position.y - 15}>{engineering(value, 'V')}</text>}
  </g>;
}

export function SchematicPart(props: PartProps) {
  const { part } = props;
  const current = props.report ? namedSignal(props.report, 'I:' + part.id) : null;
  const select = () => { props.onSelect(); if (props.observation?.observing && part.kind !== 'GND') props.observation.onCurrent(part.id); };
  return <g>
    <g className={'schematic-part ' + (props.selected ? 'selected-part' : '')} role="button"
      tabIndex={props.disabled ? -1 : 0} aria-label={'Select ' + part.id + ' ' + partValue(part)}
      aria-pressed={props.selected} onKeyDown={event => partKey(event, { ...props, onSelect: select })}
      onClick={event => { event.stopPropagation(); select(); }}
      onPointerDown={props.onStartDrag}>
      <rect className="part-hitbox" x={part.x * GRID - 48} y={part.y * GRID - 48} width="96" height="96" rx="8" />
      <g className="symbol" transform={'translate(' + part.x * GRID + ' ' + part.y * GRID + ') rotate(' + part.rotation + ')'}>
        <SchematicSymbol kind={part.kind} />
      </g>
      <text className="part-label" x={part.x * GRID + 48} y={part.y * GRID - 27}>{part.id}</text>
      <text className="part-value" x={part.x * GRID + 48} y={part.y * GRID - 7}>{partValue(part)}</text>
      {current && props.report && <text className="current-reading" x={part.x * GRID + 86} y={part.y * GRID + 18}>
        I {signalReading(props.report, current, props.frame)} {props.report.analysis !== 'ac' && '(0→1)'}</text>}
      {props.selected && props.report && props.observation?.observing && part.kind !== 'GND' &&
        <text className="current-reading" x={part.x * GRID + 86} y={part.y * GRID + 40}>ΔV {signalReading(props.report,
          probeSignal(props.report, { kind: 'differential', first: { part: part.id, terminal: 0 }, second: { part: part.id, terminal: 1 } }), props.frame)}</text>}
    </g>
    {pinsFor(part).map(pin => <Terminal key={pinKey(pin)} pin={pin} props={props} />)}
    {props.report && props.observation?.observing && <BranchDirection part={part} report={props.report} frame={props.frame} observation={props.observation} />}
  </g>;
}
