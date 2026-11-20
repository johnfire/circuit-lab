import { translate } from './localization.ts';
export interface DisplayControls {
  markers: boolean; shading: boolean; beside: boolean;
  setMarkers: (next: boolean) => void; setShading: (next: boolean) => void; setBeside: (next: boolean) => void;
}

import { engineering } from './schematic-model';

export function ObservationDisplayControls({ controls, frequency, voltageLimit }: { controls: DisplayControls; frequency: boolean; voltageLimit: number }) {
  return <div className="observation-display-controls">
    <label className="checkbox-label"><input type="checkbox" disabled={frequency} checked={!frequency && controls.markers}
      onChange={event => controls.setMarkers(event.target.checked)} />{translate("observation-display-controls.moving_current_markers")}</label>
    <label className="checkbox-label"><input type="checkbox" disabled={frequency} checked={!frequency && controls.shading}
      onChange={event => controls.setShading(event.target.checked)} />{translate("observation-display-controls.voltage_shading")}</label>
    <label className="checkbox-label"><input type="checkbox" checked={controls.beside}
      onChange={event => controls.setBeside(event.target.checked)} />{translate("observation-display-controls.scope_beside_grid_on_wide")}</label>
    <p className="muted">{translate("observation-display-controls.conventional_current_arrows_reverse_at")}</p>
    {controls.shading && !frequency && <p className="voltage-legend">{translate("observation-display-controls.fixed_fullrun_scale_blue")}{engineering(-voltageLimit, 'V')}{translate("observation-display-controls.brown_0_v_gold")}{engineering(voltageLimit, 'V')}{translate("observation-display-controls.relative_to_ground_numbers_always")}</p>}
  </div>;
}
