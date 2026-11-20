import { displayMessage } from './display-message.ts';
import { translate } from './localization.ts';
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
  return <div className="probe-panel"><label>{translate("observation-probes-panel.probe_tool")}<select aria-label={translate("observation-probes-panel.probe_tool")} value={controller.tool}
    onChange={event => controller.chooseTool(event.target.value as 'node' | 'current' | 'differential')}>
    <option value="node">{translate("observation-probes-panel.node_voltage")}</option><option value="current">{translate("observation-probes-panel.branch_current")}</option><option value="differential">{translate("observation-probes-panel.differential_voltage_two_terminals")}</option></select></label>
    <label>{translate("observation-probes-panel.probe_terminal")}<select aria-label={translate("observation-probes-panel.probe_terminal")} value={chosen ? pinKey(chosen) : ''} onChange={event => setSelected(event.target.value)}>
      {pins.map(pin => <option key={pinKey(pin)} value={pinKey(pin)}>{pinKey(pin)}</option>)}</select></label>
    <button disabled={!chosen} onClick={() => { if (chosen) controller.pin(chosen); }}>{translate("observation-probes-panel.pin_probe")}</button>
    <p role="status">{controller.message ? displayMessage(controller.message) : translate("observation-probes-panel.in_observe_mode_click_a")}</p>
    <div className="probe-chips">{controller.probes.map(probe => <button key={probeKey(probe)}
      aria-label={translate("observation-probes-panel.remove_probe") + probeKey(probe)} onClick={() => controller.remove(probe)}>{probeKey(probe)} ×</button>)}</div>
  </div>;
}
