import { useState } from 'react';
import type { Schematic } from './schematic-types';
import type { useAnalogPlayback } from './use-analog-playback';

export function ObservationCycleControls({ schematic, playback }: { schematic: Schematic; playback: ReturnType<typeof useAnalogPlayback> }) {
  const sources = schematic.parts.filter(part => part.sine);
  const [source, setSource] = useState('');
  const reference = sources.find(part => part.id === source) ?? sources[0];
  if (!reference?.sine) return null;
  const period = 1 / reference.sine.frequency;
  return <div className="cycle-controls"><label>Cycle reference<select value={reference.id} onChange={event => setSource(event.target.value)}>
    {sources.map(part => <option key={part.id}>{part.id}</option>)}</select></label>
    <button onClick={() => playback.seek(playback.cursor - period)}>Previous cycle</button>
    <button onClick={() => playback.seek(playback.cursor + period)}>Next cycle</button>
    <button onClick={() => playback.window([Math.max(0, schematic.timing.stop - 3 * period), schematic.timing.stop])}>Last three cycles</button>
    <p className="muted">{Math.floor(period / schematic.timing.step)} output samples/cycle. Aim for ≥100; refine and compare for fast changes. Startup is included until you narrow the window.</p>
    {period / schematic.timing.step < 100 && <p role="status">Sampling warning: fewer than 100 samples per reference cycle. Choose a smaller sample interval in Build mode and compare results; slow playback cannot restore missing samples.</p>}
  </div>;
}
