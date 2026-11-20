import { translate } from './localization.ts';
import { useState } from 'react';
import type { Schematic } from './schematic-types';
import type { useAnalogPlayback } from './use-analog-playback';

export function ObservationCycleControls({ schematic, playback }: { schematic: Schematic; playback: ReturnType<typeof useAnalogPlayback> }) {
  const sources = schematic.parts.filter(part => part.sine);
  const [source, setSource] = useState('');
  const reference = sources.find(part => part.id === source) ?? sources[0];
  if (!reference?.sine) return null;
  const period = 1 / reference.sine.frequency;
  return <div className="cycle-controls"><label>{translate("observation-cycle-controls.cycle_reference")}<select value={reference.id} onChange={event => setSource(event.target.value)}>
    {sources.map(part => <option key={part.id}>{part.id}</option>)}</select></label>
    <button onClick={() => playback.seek(playback.cursor - period)}>{translate("observation-cycle-controls.previous_cycle")}</button>
    <button onClick={() => playback.seek(playback.cursor + period)}>{translate("observation-cycle-controls.next_cycle")}</button>
    <button onClick={() => playback.window([Math.max(0, schematic.timing.stop - 3 * period), schematic.timing.stop])}>{translate("observation-cycle-controls.last_three_cycles")}</button>
    <p className="muted">{Math.floor(period / schematic.timing.step)}{translate("observation-cycle-controls.output_samplescycle_aim_for_100")}</p>
    {period / schematic.timing.step < 100 && <p role="status">{translate("observation-cycle-controls.sampling_warning_fewer_than_100")}</p>}
  </div>;
}
