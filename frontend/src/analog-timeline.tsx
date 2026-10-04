import { engineering } from './schematic-model';
import type { AnalogReport } from './schematic-types';
import type { useAnalogPlayback } from './use-analog-playback';

type Playback = ReturnType<typeof useAnalogPlayback>;

export function AnalogTimeline({ playback, report }: { playback: Playback; report: AnalogReport }) {
  const frameTime = report.times[playback.index];
  return <section className="editor-card timeline-panel" aria-label="Simulation playback"><div className="timeline-heading">
    <h2>Watch the circuit</h2><output aria-label="Frame time">{engineering(frameTime, 's')} · frame {playback.index + 1}/{report.times.length}</output></div>
    <div className="compact-fields interval-fields"><label>Watch from (ms)<input type="number" step="any" min="0"
      max={playback.bounds[1] * 1000} value={playback.bounds[0] * 1000}
      onChange={event => playback.window([Number(event.target.value) / 1000, playback.bounds[1]])} /></label>
      <label>Watch until (ms)<input type="number" step="any" min={playback.bounds[0] * 1000} max={(report.times.at(-1) ?? 0) * 1000}
        value={playback.bounds[1] * 1000} onChange={event => playback.window([playback.bounds[0], Number(event.target.value) / 1000])} /></label></div>
    <p className="muted">Playback speed changes how fast you watch, not the circuit physics. All on-grid readings use the same sampled instant.</p>
  </section>;
}
