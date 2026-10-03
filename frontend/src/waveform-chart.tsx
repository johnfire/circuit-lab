import { useState } from 'react';
import type { Signal } from './circuit-types';

const COLORS = ['var(--color-signal-0)', 'var(--color-signal-1)', 'var(--color-signal-2)'];
interface Props { signals: Signal[]; isDc: boolean }
interface ChartRange { maximumX: number; startX: number; minimumY: number; maximumY: number; ySpan: number; xSpan: number }

export function WaveformChart({ signals, isDc }: Props) {
  const [zoom, setZoom] = useState(1);
  const [cursor, setCursor] = useState(0.5);
  const allPoints = signals.flatMap(signal => signal.points);
  const maximumX = Math.max(...allPoints.map(point => point[0]));
  const startX = maximumX * (1 - 1 / zoom);
  const minimumY = Math.min(0, ...signals.map(signal => signal.minimum));
  const maximumY = Math.max(0.1, ...signals.map(signal => signal.maximum));
  const ySpan = Math.max(maximumY - minimumY, 0.1);
  const xSpan = Math.max(maximumX - startX, 1e-12);
  const cursorX = startX + cursor * xSpan;
  const xLabel = (value: number) => isDc ? value.toFixed(2) + ' V' : (value * 1000).toPrecision(3) + ' ms';
  const range = { maximumX, startX, minimumY, maximumY, ySpan, xSpan };
  return <section aria-labelledby="waveform-heading">
    <div className="section-heading"><h2 id="waveform-heading">Waveforms</h2>
      <label className="zoom-label">View
        <select aria-label="Waveform zoom" value={zoom} onChange={event => setZoom(Number(event.target.value))}>
          <option value={1}>Full trace</option><option value={4}>Last quarter</option>
          <option value={16}>Last 1/16</option>
        </select></label></div>
    <WaveformPlot signals={signals} range={range} cursor={cursor} xLabel={xLabel} />
    <div className="signal-legend">{signals.map((signal, index) => <span key={signal.name}>
      <i className={'signal-color color-' + index % COLORS.length} />{signal.name}
    </span>)}</div>
    <label className="cursor-control">Measurement cursor · {xLabel(cursorX)}
      <input type="range" min="0" max="1" step="0.001" value={cursor}
        onChange={event => setCursor(Number(event.target.value))} />
    </label>
    <CursorMeasurements signals={signals} cursorX={cursorX} />
  </section>;
}

function WaveformPlot({ signals, range, cursor, xLabel }: {
  signals: Signal[]; range: ChartRange; cursor: number; xLabel: (value: number) => string;
}) {
  const { startX, xSpan, minimumY, ySpan, maximumY } = range;
  const pathFor = (signal: Signal) => signal.points.filter(point => point[0] >= startX)
    .map(([time, voltage], index) => (index === 0 ? 'M' : 'L') +
      (60 + (time - startX) / xSpan * 670) + ',' + (250 - (voltage - minimumY) / ySpan * 210))
    .join(' ');
  return <svg className="waveform" viewBox="0 0 780 300" role="img" aria-label="Voltage waveforms from ngspice">
      {[0, 1, 2, 3, 4].map(index => <g key={index}>
        <line x1="60" x2="730" y1={40 + index * 52.5} y2={40 + index * 52.5} className="chart-grid" />
        <text x="48" y={44 + index * 52.5} textAnchor="end">
          {(maximumY - index / 4 * ySpan).toFixed(2)}</text>
      </g>)}
      {signals.map((signal, index) => <path key={signal.name} d={pathFor(signal)} fill="none"
        stroke={COLORS[index % COLORS.length]} strokeWidth="2" />)}
      <line x1={60 + cursor * 670} x2={60 + cursor * 670} y1="35" y2="250" className="chart-cursor" />
      {[0, 0.25, 0.5, 0.75, 1].map(fraction => <text key={fraction}
        x={60 + fraction * 670} y="278" textAnchor="middle">{xLabel(startX + fraction * xSpan)}</text>)}
      <text x="18" y="24">V</text>
    </svg>;
}

function CursorMeasurements({ signals, cursorX }: { signals: Signal[]; cursorX: number }) {
  return <div className="measurements">{signals.map(signal => {
      const nearest = signal.points.reduce((closest, point) =>
        Math.abs(point[0] - cursorX) < Math.abs(closest[0] - cursorX) ? point : closest);
      return <div key={signal.name}><span>{signal.name}</span><strong>{nearest[1].toFixed(4)} V</strong>
        <small>at nearest plotted sample</small></div>;
    })}</div>;
}
