import type { ACReport, AnalogReport, Schematic, Sweep } from './schematic-types';

export async function simulateAC(schematic: Schematic, sweep: Sweep): Promise<ACReport> {
  return await requestAnalysis('/api/schematic/ac', { circuit: schematic, sweep }) as ACReport;
}

export async function simulateAnalog(schematic: Schematic): Promise<AnalogReport> {
  return await requestAnalysis('/api/schematic/simulate', schematic) as AnalogReport;
}

async function requestAnalysis(endpoint: string, circuit: unknown): Promise<unknown> {
  const response = await fetch(endpoint, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(circuit),
    signal: AbortSignal.timeout(20000) });
  const submitted: unknown = await response.json();
  if (!response.ok) {
    throw new Error(analysisFailureMessage(submitted));
  }
  return submitted;
}

/** Surface bounded server validation messages, never the submitted raw input. */
export function analysisFailureMessage(submitted: unknown): string {
  const detail = typeof submitted === 'object' && submitted !== null && 'detail' in submitted ? submitted.detail : '';
  if (typeof detail === 'string' && detail) return detail.slice(0, 500);
  if (Array.isArray(detail)) {
    const messages = detail.filter(entry => typeof entry === 'object' && entry !== null && 'msg' in entry && typeof entry.msg === 'string')
      .slice(0, 3).map(entry => String(entry.msg).slice(0, 200));
    if (messages.length) return messages.join('; ');
  }
  return 'Check component values, wiring and analysis settings.';
}
