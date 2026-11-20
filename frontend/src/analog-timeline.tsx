import { translate } from './localization.ts';
import { engineering } from './schematic-model';
import type { AnalogReport } from './schematic-types';
import type { useAnalogPlayback } from './use-analog-playback';

type Playback = ReturnType<typeof useAnalogPlayback>;

export function AnalogTimeline({ playback, report }: { playback: Playback; report: AnalogReport }) {
  const frameTime = report.times[playback.index];
  return <section className="editor-card timeline-panel" aria-label={translate("analog-timeline.simulation_playback")}><div className="timeline-heading">
    <h2>{translate("analog-timeline.watch_the_circuit")}</h2><output aria-label={translate("analog-timeline.frame_time")}>{engineering(frameTime, 's')}{translate("analog-timeline.frame")}{playback.index + 1}/{report.times.length}</output></div>
    <div className="compact-fields interval-fields"><label>{translate("analog-timeline.watch_from_ms")}<input type="number" step="any" min="0"
      max={playback.bounds[1] * 1000} value={playback.bounds[0] * 1000}
      onChange={event => playback.window([Number(event.target.value) / 1000, playback.bounds[1]])} /></label>
      <label>{translate("analog-timeline.watch_until_ms")}<input type="number" step="any" min={playback.bounds[0] * 1000} max={(report.times.at(-1) ?? 0) * 1000}
        value={playback.bounds[1] * 1000} onChange={event => playback.window([playback.bounds[0], Number(event.target.value) / 1000])} /></label></div>
    <p className="muted">{translate("analog-timeline.playback_speed_changes_how_fast")}</p>
  </section>;
}
