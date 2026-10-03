export type PartKind = 'R' | 'C' | 'L' | 'V' | 'PULSE' | 'GND';
export type Rotation = 0 | 90 | 180 | 270;
export interface Pulse { period: number; width: number; delay: number }
export interface Part {
  id: string; kind: PartKind; value: number; x: number; y: number;
  rotation: Rotation; pulse?: Pulse | null;
}
export interface Pin { part: string; terminal: 0 | 1 }
export interface Wire { a: Pin; b: Pin }
export interface Schematic { parts: Part[]; wires: Wire[]; timing: { stop: number; step: number } }
export interface AnalogTrace { name: string; unit: 'V' | 'A'; values: number[] }
export interface AnalogReport {
  status: 'completed'; correlation_id: string; times: number[]; traces: AnalogTrace[];
  pin_nodes: Record<string, string>; warnings: string[]; netlist: string;
}
export interface EditorAction {
  timestamp: string; actor: 'user:browser'; action: string; correlation_id: string; outcome: 'success';
}
