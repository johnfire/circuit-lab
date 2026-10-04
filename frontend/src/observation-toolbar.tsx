import { engineering } from './schematic-model';
import type { EditorState } from './use-schematic-editor';
import type { useAnalogPlayback } from './use-analog-playback';
import type { ACReport, AnalogReport } from './schematic-types';

export interface ObservationControls { observing: boolean; setObserving: (next: boolean) => void }
type Playback = ReturnType<typeof useAnalogPlayback>;

export function ObservationToolbar({ editor, controls, children }: {
  editor: EditorState; controls: ObservationControls; children?: React.ReactNode;
}) {
  return <section className="editor-card observation-toolbar" aria-label="Circuit observation controls">
    <div className="observation-mode-controls"><button aria-pressed={!controls.observing} onClick={() => controls.setObserving(false)}>Build</button>
      <button aria-pressed={controls.observing} onClick={() => { editor.setArmed(null); editor.setWireStart(null); controls.setObserving(true); }}>Observe</button>
      <label>Analysis<select aria-label="Analysis" disabled={editor.running} value={editor.analysis}
        onChange={event => editor.setAnalysis(event.target.value as 'transient' | 'ac')}>
        <option value="transient">Time domain</option><option value="ac">Frequency sweep</option></select></label>
      <button disabled={editor.running} className="run-button" onClick={() => { void editor.run(); }}>{editor.running ? 'Computing…' : 'Run analysis'}</button>
    </div>{children}
  </section>;
}

export function TimePlaybackControls({ playback, report }: { playback: Playback; report: AnalogReport }) {
  return <><div className="playback-controls"><button onClick={() => playback.seek(playback.bounds[0])} aria-label="Rewind">↤</button>
    <button onClick={() => playback.step(-1)} aria-label="Previous frame">◀</button>
    <button className="play-toggle" onClick={playback.toggle}>{playback.playing ? 'Pause' : 'Play'}</button>
    <button onClick={() => playback.step(1)} aria-label="Next frame">▶</button>
    <label>Playback rate<select value={playback.rate} onChange={event => playback.setRate(Number(event.target.value))}>
      <option value={.001}>1 ms / real second</option><option value={.01}>10 ms / real second</option>
      <option value={.1}>100 ms / real second</option><option value={1}>Real time (1×)</option></select></label>
    <label className="checkbox-label"><input type="checkbox" checked={playback.loop} onChange={event => playback.setLoop(event.target.checked)} />Loop</label>
    <output aria-label="Grid observation time">{engineering(report.times[playback.index], 's')}</output></div>
    <label className="time-scrubber">Time cursor<input type="range" min={playback.bounds[0]} max={playback.bounds[1]}
      step={report.times[1] - report.times[0]} value={playback.cursor} onChange={event => playback.seek(Number(event.target.value))} /></label>
  </>;
}

export function FrequencyCursor({ report, frame, onSeek }: { report: ACReport; frame: number; onSeek: (index: number) => void }) {
  return <><div className="playback-controls"><button aria-label="Previous frequency" onClick={() => onSeek(Math.max(0, frame - 1))}>◀</button>
    <button aria-label="Next frequency" onClick={() => onSeek(Math.min(report.frequencies.length - 1, frame + 1))}>▶</button>
    <output aria-label="Grid observation frequency">{engineering(report.frequencies[frame], 'Hz')} · {frame + 1}/{report.frequencies.length}</output></div>
    <label>Frequency cursor<input type="range" min="0" max={report.frequencies.length - 1} step="1" value={frame}
      onChange={event => onSeek(Number(event.target.value))} /></label>
    <p className="muted">Amplitude ∠ phase, relative to excitation. This view does not animate time or current flow.</p>
  </>;
}
