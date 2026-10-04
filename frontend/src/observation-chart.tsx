import { extremaIndices } from './observation-signals';
import { engineering } from './schematic-model';

export interface PlotSeries { label: string; coefficients: (number | null)[]; color: string }
interface PlotProps {
  title: string; unit: string; axis: number[]; series: PlotSeries[]; index: number;
  logarithmic: boolean; bounds: [number, number]; onSeek: (index: number) => void; phaseWrapped?: boolean;
}

function axisFraction(coordinate: number, bounds: [number, number], logarithmic: boolean): number {
  const transform = logarithmic ? Math.log10 : (coefficient: number) => coefficient;
  return (transform(coordinate) - transform(bounds[0])) / (transform(bounds[1]) - transform(bounds[0]));
}

function plotPath(axis: number[], coefficients: (number | null)[], props: PlotProps, range: [number, number]): string {
  let path = '', previous: number | null = null;
  const indices = extremaIndices(coefficients);
  for (const index of indices) {
    const coefficient = coefficients[index];
    if (axis[index] < props.bounds[0] || axis[index] > props.bounds[1] || coefficient === null) { previous = null; continue; }
    const horizontal = 54 + 660 * axisFraction(axis[index], props.bounds, props.logarithmic);
    const vertical = 130 - 104 * (coefficient - range[0]) / (range[1] - range[0]);
    const move = previous === null || (props.phaseWrapped && Math.abs(coefficient - previous) > 180);
    path += (move ? 'M' : ' L') + horizontal.toFixed(2) + ' ' + vertical.toFixed(2);
    previous = coefficient;
  }
  return path;
}

function plotRange(props: PlotProps): [number, number] {
  const coefficients = props.series.flatMap(series => series.coefficients.filter((coefficient, index): coefficient is number =>
    coefficient !== null && props.axis[index] >= props.bounds[0] && props.axis[index] <= props.bounds[1]));
  if (!coefficients.length) return [-1, 1];
  const low = Math.min(...coefficients), high = Math.max(...coefficients);
  const padding = Math.max((high - low) * .08, Math.abs(high) * .03, 1e-12);
  return [low - padding, high + padding];
}

export function ObservationChart(props: PlotProps) {
  const range = plotRange(props);
  const cursor = 54 + 660 * axisFraction(props.axis[props.index], props.bounds, props.logarithmic);
  return <div className="observation-plot"><h3>{props.title} · {props.unit}</h3>
    <svg viewBox="0 0 760 164" role="slider" tabIndex={0} aria-label={'Seek ' + props.title.toLowerCase() + ' plot'}
      aria-valuemin={0} aria-valuemax={props.axis.length - 1} aria-valuenow={props.index}
      aria-valuetext={engineering(props.axis[props.index], props.logarithmic ? 'Hz' : '')}
      onKeyDown={event => { const moves: Record<string, number> = { ArrowLeft: props.index - 1, ArrowRight: props.index + 1, Home: 0, End: props.axis.length - 1 };
        if (moves[event.key] !== undefined) { event.preventDefault(); props.onSeek(Math.max(0, Math.min(props.axis.length - 1, moves[event.key]))); } }}
      onPointerDown={event => { const rectangle = event.currentTarget.getBoundingClientRect();
        const fraction = Math.max(0, Math.min(1, ((event.clientX - rectangle.left) * 760 / rectangle.width - 54) / 660));
        const coordinate = props.logarithmic ? props.bounds[0] * (props.bounds[1] / props.bounds[0]) ** fraction
          : props.bounds[0] + (props.bounds[1] - props.bounds[0]) * fraction;
        const index = props.axis.reduce((nearest, sample, index) => Math.abs(sample - coordinate) < Math.abs(props.axis[nearest] - coordinate) ? index : nearest, 0);
        props.onSeek(index); }}>
      {[26, 78, 130].map(vertical => <path key={vertical} className="scope-gridline" d={'M54 ' + vertical + ' H714'} />)}
      <text x="4" y="30">{engineering(range[1])}</text><text x="4" y="133">{engineering(range[0])}</text>
      <text x="54" y="155">{engineering(props.bounds[0])}</text><text x="650" y="155">{engineering(props.bounds[1])}</text>
      {props.series.map(series => <path key={series.label} className="scope-trace" stroke={series.color} d={plotPath(props.axis, series.coefficients, props, range)} />)}
      {cursor >= 54 && cursor <= 714 && <path className="scope-cursor" d={'M' + cursor + ' 20 V136'} />}
    </svg>
    <div className="scope-legend">{props.series.map(series => <span key={series.label} style={{ borderColor: series.color }}>{series.label}</span>)}</div>
  </div>;
}
