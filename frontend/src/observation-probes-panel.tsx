import { useState } from 'react';
import { pinKey, pinsFor } from './schematic-model';
import { probeKey } from './observation-signals';
import type { Schematic } from './schematic-types';
import type { useObservationProbes } from './use-observation-probes';

export type ProbeController = ReturnType<typeof useObservationProbes>;

export function ObservationProbesPanel({ schematic, controller }: { schematic: Schematic; controller: ProbeController }) {
  const pins = schematic.parts.flatMap(pinsFor);
  const [selected, setSelected] = useState('');
  const chosen = pins.find(pin => pinKey(pin) === selected) ?? pins[0];
  return <div className="probe-panel"><label>Probe tool<select aria-label="Probe tool" value={controller.tool}
    onChange={event => controller.chooseTool(event.target.value as 'node' | 'current' | 'differential')}>
    <option value="node">Node voltage</option><option value="current">Branch current</option><option value="differential">Differential voltage (two terminals)</option></select></label>
    <label>Probe terminal<select aria-label="Probe terminal" value={chosen ? pinKey(chosen) : ''} onChange={event => setSelected(event.target.value)}>
      {pins.map(pin => <option key={pinKey(pin)} value={pinKey(pin)}>{pinKey(pin)}</option>)}</select></label>
    <button disabled={!chosen} onClick={() => { if (chosen) controller.pin(chosen); }}>Pin probe</button>
    <p role="status">{controller.message || 'In Observe mode, click a terminal or symbol, or pin a probe here. Maximum eight.'}</p>
    <div className="probe-chips">{controller.probes.map(probe => <button key={probeKey(probe)}
      aria-label={'Remove probe ' + probeKey(probe)} onClick={() => controller.remove(probe)}>{probeKey(probe)} ×</button>)}</div>
  </div>;
}
