import type { AnalogReport, Schematic } from './schematic-types';

export async function simulateAnalog(schematic: Schematic): Promise<AnalogReport> {
  const response = await fetch('/api/schematic/simulate', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(schematic),
    signal: AbortSignal.timeout(20000) });
  const submitted: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof submitted === 'object' && submitted !== null && 'detail' in submitted ? submitted.detail : '';
    throw new Error(typeof detail === 'string' && detail ? detail : 'Check component values, wiring and time settings.');
  }
  return submitted as AnalogReport;
}
