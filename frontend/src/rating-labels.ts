import { translatedLabels } from './localization.ts';

export const RATING_LABELS: Record<string, string> = translatedLabels({
  if_max: "analog-ratings.forward_current", vr_max: "analog-ratings.reverse_voltage", iz_max: "analog-ratings.zener_current", pd_max: "analog-ratings.power_dissipation",
  vds_max: "analog-ratings.drainsource_voltage", vgs_max: "analog-ratings.gatesource_voltage", id_max: "analog-ratings.drain_current",
  vceo_max: "analog-ratings.collectoremitter_voltage", ic_max: "analog-ratings.collector_current", vs_max: "analog-ratings.supply_voltage", iout_max: "analog-ratings.output_current",
  vin_max: "analog-ratings.input_voltage", pin_current_max: "analog-ratings.pin_current", pin_voltage_max: "analog-ratings.pin_voltage",
  pin_negative_voltage_max: "analog-ratings.voltage_below_ground", supply_current_max: "analog-ratings.supply_current",
  power_max: "analog-ratings.power", voltage_max: "analog-ratings.voltage", reverse_voltage_max: "analog-ratings.reverse_voltage_electrolytic",
});
