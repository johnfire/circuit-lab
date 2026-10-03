import { engineering } from './schematic-model';
import type { AnalogReport } from './schematic-types';
import type { useAnalogPlayback } from './use-analog-playback';

type Playback = ReturnType<typeof useAnalogPlayback>;

export function AnalogTimeline({ playback, report }: { playback: Playback; report: AnalogReport }) {
  const frameTime = report.times[playback.index];
  return <section className="editor-card timeline-panel" aria-label="Simulation playback"><div className="timeline-heading">
    <h2>Watch the circuit</h2><output aria-label="Frame time">{engineering(frameTime, 's')} · frame {playback.index + 1}/{report.times.length}</output></div>
    <label className="time-scrubber">Time cursor<input type="range" min={playback.bounds[0]} max={playback.bounds[1]}
      step={report.times[1] - report.times[0]} value={playback.cursor} onChange={event => playback.seek(Number(event.target.value))} /></label>
    <div className="playback-controls"><button onClick={() => playback.seek(playback.bounds[0])} aria-label="Rewind">↤</button>
      <button onClick={() => playback.step(-1)} aria-label="Previous frame">◀</button>
      <button className="play-toggle" onClick={playback.toggle}>{playback.playing ? 'Pause' : 'Play'}</button>
      <button onClick={() => playback.step(1)} aria-label="Next frame">▶</button>
      <label>Playback rate<select value={playback.rate} onChange={event => playback.setRate(Number(event.target.value))}>
        <option value={.001}>1 ms / real second</option><option value={.01}>10 ms / real second</option>
        <option value={.1}>100 ms / real second</option><option value={1}>Real time (1×)</option></select></label>
      <label className="checkbox-label"><input type="checkbox" checked={playback.loop} onChange={event => playback.setLoop(event.target.checked)} />Loop</label></div>
    <div className="compact-fields interval-fields"><label>Watch from (ms)<input type="number" step="any" min="0"
      max={playback.bounds[1] * 1000} value={playback.bounds[0] * 1000}
      onChange={event => playback.window([Number(event.target.value) / 1000, playback.bounds[1]])} /></label>
      <label>Watch until (ms)<input type="number" step="any" min={playback.bounds[0] * 1000} max={(report.times.at(-1) ?? 0) * 1000}
        value={playback.bounds[1] * 1000} onChange={event => playback.window([playback.bounds[0], Number(event.target.value) / 1000])} /></label></div>
    <p className="muted">Playback speed changes how fast you watch, not the circuit physics. All on-grid readings use the same sampled instant.</p>
  </section>;
}
