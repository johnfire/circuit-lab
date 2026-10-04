export interface DisplayControls {
  markers: boolean; shading: boolean; beside: boolean;
  setMarkers: (next: boolean) => void; setShading: (next: boolean) => void; setBeside: (next: boolean) => void;
}

import { engineering } from './schematic-model';

export function ObservationDisplayControls({ controls, frequency, voltageLimit }: { controls: DisplayControls; frequency: boolean; voltageLimit: number }) {
  return <div className="observation-display-controls">
    <label className="checkbox-label"><input type="checkbox" disabled={frequency} checked={!frequency && controls.markers}
      onChange={event => controls.setMarkers(event.target.checked)} />Moving current markers</label>
    <label className="checkbox-label"><input type="checkbox" disabled={frequency} checked={!frequency && controls.shading}
      onChange={event => controls.setShading(event.target.checked)} />Voltage shading</label>
    <label className="checkbox-label"><input type="checkbox" checked={controls.beside}
      onChange={event => controls.setBeside(event.target.checked)} />Scope beside grid on wide screens</label>
    <p className="muted">Conventional current: arrows reverse at negative current. Markers are explanatory, not electron speed. Only component branch currents are shown; ideal-wire loop currents are not inferred.</p>
    {controls.shading && !frequency && <p className="voltage-legend">Fixed full-run scale: blue {engineering(-voltageLimit, 'V')} ↔ brown 0 V ↔ gold {engineering(voltageLimit, 'V')}, relative to ground. Numbers always give the exact reading.</p>}
  </div>;
}
