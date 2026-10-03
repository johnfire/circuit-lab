export interface Parameter {
  name: string;
  value: number;
  unit: string;
  minimum: number;
  maximum: number;
}

export interface Component {
  name: string;
  kind: string;
  nodes: string[];
  value: string;
}

export interface Circuit {
  id: string;
  title: string;
  description: string;
  category: string;
  parameters: Parameter[];
  components: Component[];
  model_trust: string;
}

export interface Signal {
  name: string;
  points: [number, number][];
  minimum: number;
  maximum: number;
  final: number;
  sample_count: number;
}

export interface SimulationReport {
  circuit_id: string;
  correlation_id: string;
  status: string;
  model_trust: string;
  parameters: Record<string, number>;
  signals: Signal[];
  checks: { name: string; passed: boolean; detail: string }[];
  warnings: string[];
  netlist: string;
  duration_ms: number;
}
