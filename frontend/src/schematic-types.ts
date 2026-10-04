export type PartKind = 'R' | 'C' | 'L' | 'V' | 'PULSE' | 'SIN' | 'GND';
export type Rotation = 0 | 90 | 180 | 270;
export interface Pulse { period: number; width: number; delay: number }
export interface Sine { offset: number; frequency: number; phase: number }
export interface Part {
  id: string; kind: PartKind; value: number; x: number; y: number;
  rotation: Rotation; pulse?: Pulse | null; sine?: Sine | null;
}
export interface Pin { part: string; terminal: 0 | 1 }
export interface Wire { a: Pin; b: Pin }
export interface Schematic { parts: Part[]; wires: Wire[]; timing: { stop: number; step: number } }
export interface AnalogTrace { name: string; unit: 'V' | 'A'; values: number[] }
export interface AnalogReport {
  analysis?: 'transient';
  status: 'completed'; correlation_id: string; times: number[]; traces: AnalogTrace[];
  pin_nodes: Record<string, string>; warnings: string[]; netlist: string;
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
  timestamp: string; actor: 'user:browser'; action: string; correlation_id: string; outcome: 'success' | 'failure';
}
