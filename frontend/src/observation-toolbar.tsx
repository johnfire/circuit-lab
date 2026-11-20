import { translate } from './localization.ts';
import { engineering } from './schematic-model';
import type { EditorState } from './use-schematic-editor';
import type { useAnalogPlayback } from './use-analog-playback';
import type { ACReport, AnalogReport } from './schematic-types';

export interface ObservationControls { observing: boolean; setObserving: (next: boolean) => void }
type Playback = ReturnType<typeof useAnalogPlayback>;

export function ObservationToolbar({ editor, controls, children }: {
  editor: EditorState; controls: ObservationControls; children?: React.ReactNode;
}) {
  return <section className="editor-card observation-toolbar" aria-label={translate("observation-toolbar.circuit_observation_controls")}>
    <div className="observation-mode-controls"><button aria-pressed={!controls.observing} onClick={() => controls.setObserving(false)}>{translate("observation-toolbar.build")}</button>
      <button aria-pressed={controls.observing} onClick={() => { editor.setArmed(null); editor.setWireStart(null); controls.setObserving(true); }}>{translate("observation-toolbar.observe")}</button>
      <label>{translate("observation-toolbar.analysis")}<select aria-label={translate("observation-toolbar.analysis")} disabled={editor.running} value={editor.analysis}
        onChange={event => editor.setAnalysis(event.target.value as 'transient' | 'ac')}>
        <option value="transient">{translate("observation-toolbar.time_domain")}</option><option value="ac">{translate("observation-toolbar.frequency_sweep")}</option></select></label>
      <button disabled={editor.running} className="run-button" onClick={() => { void editor.run(); }}>{editor.running ? translate('common.simulating') : translate("observation-toolbar.run_analysis")}</button>
    </div>{children}
  </section>;
}

export function TimePlaybackControls({ playback, report }: { playback: Playback; report: AnalogReport }) {
  return <><div className="playback-controls"><button onClick={() => playback.seek(playback.bounds[0])} aria-label={translate("observation-toolbar.rewind")}>↤</button>
    <button onClick={() => playback.step(-1)} aria-label={translate("observation-toolbar.previous_frame")}>◀</button>
    <button className="play-toggle" onClick={playback.toggle}>{playback.playing ? translate("observation-toolbar.pause") : translate("observation-toolbar.play")}</button>
    <button onClick={() => playback.step(1)} aria-label={translate("observation-toolbar.next_frame")}>▶</button>
    <label>{translate("observation-toolbar.playback_rate")}<select value={playback.rate} onChange={event => playback.setRate(Number(event.target.value))}>
      <option value={.001}>{translate("observation-toolbar.1_ms_real_second")}</option><option value={.01}>{translate("observation-toolbar.10_ms_real_second")}</option>
      <option value={.1}>{translate("observation-toolbar.100_ms_real_second")}</option><option value={1}>{translate("observation-toolbar.real_time_1")}</option></select></label>
    <label className="checkbox-label"><input type="checkbox" checked={playback.loop} onChange={event => playback.setLoop(event.target.checked)} />{translate("observation-toolbar.loop")}</label>
    <output aria-label={translate("observation-toolbar.grid_observation_time")}>{engineering(report.times[playback.index], 's')}</output></div>
    <label className="time-scrubber">{translate("observation-toolbar.time_cursor")}<input type="range" min={playback.bounds[0]} max={playback.bounds[1]}
      step={report.times[1] - report.times[0]} value={playback.cursor} onChange={event => playback.seek(Number(event.target.value))} /></label>
  </>;
}

export function FrequencyCursor({ report, frame, onSeek }: { report: ACReport; frame: number; onSeek: (index: number) => void }) {
  return <><div className="playback-controls"><button aria-label={translate("observation-toolbar.previous_frequency")} onClick={() => onSeek(Math.max(0, frame - 1))}>◀</button>
    <button aria-label={translate("observation-toolbar.next_frequency")} onClick={() => onSeek(Math.min(report.frequencies.length - 1, frame + 1))}>▶</button>
    <output aria-label={translate("observation-toolbar.grid_observation_frequency")}>{engineering(report.frequencies[frame], 'Hz')} · {frame + 1}/{report.frequencies.length}</output></div>
    <label>{translate("observation-toolbar.frequency_cursor")}<input type="range" min="0" max={report.frequencies.length - 1} step="1" value={frame}
      onChange={event => onSeek(Number(event.target.value))} /></label>
    <p className="muted">{translate("observation-toolbar.amplitude_phase_relative_to_excitation")}</p>
  </>;
}
