export type DeviceKind = 'D' | 'NMOS' | 'PMOS' | 'NPN' | 'PNP' | 'OPAMP' | 'REG';
export type PartKind = 'R' | 'C' | 'L' | 'V' | 'PULSE' | 'SIN' | 'GND' | 'PIN' | DeviceKind;
export type PinMode = 'output_high' | 'output_low' | 'pulse' | 'input' | 'input_pull_up' | 'input_pull_down' | 'supply';
export interface BoardPinSettings { board: string; pin: string; mode: PinMode }
export type Terminal = 0 | 1 | 2 | 3 | 4;
export type Rotation = 0 | 90 | 180 | 270;
export interface Pulse { period: number; width: number; delay: number }
export interface Sine { offset: number; frequency: number; phase: number }
export interface Part {
  id: string; kind: PartKind; value: number; x: number; y: number;
  rotation: Rotation; pulse?: Pulse | null; sine?: Sine | null; device?: string | null;
  board_pin?: BoardPinSettings | null; footprint?: string | null;
}
export interface Pin { part: string; terminal: Terminal }
export interface Wire { a: Pin; b: Pin }
export interface Schematic { parts: Part[]; wires: Wire[]; timing: { stop: number; step: number } }
export interface AnalogTrace { name: string; unit: 'V' | 'A'; values: number[] }
export interface RatingCheck {
  part: string; device: string; rating: string; statistic: 'peak' | 'average'; measured: number;
  limit: number; unit: 'V' | 'A' | 'W'; passed: boolean; trust: 'draft' | 'verified';
}
export interface AnalogReport {
  analysis?: 'transient';
  status: 'completed'; correlation_id: string; times: number[]; traces: AnalogTrace[];
  pin_nodes: Record<string, string>; warnings: string[]; netlist: string; ratings?: RatingCheck[];
}
export interface Sweep {
  source: string; amplitude: number; phase: number; start: number; stop: number;
  spacing: 'log' | 'linear'; points: number;
}
export interface ComplexTrace { name: string; unit: 'V' | 'A'; real: number[]; imaginary: number[] }
export interface ACReport {
  analysis: 'ac'; status: 'completed'; correlation_id: string; frequencies: number[];
  traces: ComplexTrace[]; pin_nodes: Record<string, string>; excitation: Sweep;
  dc_biases: Record<string, number>; warnings: string[]; netlist: string;
}
export type ObservationReport = AnalogReport | ACReport;
export type Probe = { kind: 'node'; pin: Pin } | { kind: 'current'; part: string }
  | { kind: 'differential'; first: Pin; second: Pin };
export interface EditorAction {
  timestamp: string; actor: string; action: string; correlation_id: string; outcome: 'success' | 'failure';
}
