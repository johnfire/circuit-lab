import type { Circuit, SimulationReport } from './circuit-types';

async function readResponse<ResponseType>(response: Response): Promise<ResponseType> {
  if (!response.ok) {
    const failure: unknown = await response.json();
    const detail = typeof failure === 'object' && failure !== null && 'detail' in failure
      ? failure.detail : undefined;
    throw new Error(typeof detail === 'string' ? detail : 'Check component values and try again.');
  }
  return response.json() as Promise<ResponseType>;
}

export async function fetchCircuits(): Promise<Circuit[]> {
  return readResponse<Circuit[]>(await fetch('/api/circuits'));
}

export async function requestSimulation(
  circuitId: string, parameters: Record<string, number>, rippleLimit: number,
): Promise<SimulationReport> {
  const response = await fetch('/api/circuits/' + encodeURIComponent(circuitId) + '/simulate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parameters, max_ripple_v: rippleLimit }),
    signal: AbortSignal.timeout(20000),
  });
  return readResponse<SimulationReport>(response);
}

export function exportReport(report: SimulationReport): void {
  const downloadUrl = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {
    type: 'application/json',
  }));
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = report.circuit_id + '-report.json';
  link.click();
  URL.revokeObjectURL(downloadUrl);
}
