import { activeLocale, translate } from './localization.ts';
import { LocalizedFailure, displayMessage, type MessageReference } from './display-message.ts';
import { parseMessage } from './report-localization.ts';
import type { ACReport, AnalogReport, Schematic, Sweep } from './schematic-types';

export async function simulateAC(schematic: Schematic, sweep: Sweep): Promise<ACReport> {
  return await requestAnalysis('/api/schematic/ac', { circuit: schematic, sweep }) as ACReport;
}

export async function simulateAnalog(schematic: Schematic): Promise<AnalogReport> {
  return await requestAnalysis('/api/schematic/simulate', schematic) as AnalogReport;
}

export interface KicadFiles { netlist: string; bom_csv: string; design_rules: string; fab_guide: string; warnings: string[]; warning_messages?: unknown[] }

export async function exportKicad(schematic: Schematic): Promise<KicadFiles> {
  return await requestAnalysis('/api/export/kicad?language=' + activeLocale(), schematic) as KicadFiles;
}

/** Simulates the circuit in the worker and returns a markdown first-power-on checklist. */
export async function exportBringUp(schematic: Schematic): Promise<string> {
  return (await requestAnalysis('/api/export/bring-up?language=' + activeLocale(), schematic) as { sheet: string }).sheet;
}

async function requestAnalysis(endpoint: string, circuit: unknown): Promise<unknown> {
  const response = await fetch(endpoint, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(circuit),
    signal: AbortSignal.timeout(20000) });
  const submitted: unknown = await response.json();
  if (!response.ok) {
    throw analysisFailure(submitted);
  }
  return submitted;
}

/** Surface bounded server validation messages, never the submitted raw input. */
export function analysisFailureMessage(submitted: unknown): string {
  const reference = failureReference(submitted);
  if (reference) return displayMessage(reference);
  const detail = typeof submitted === 'object' && submitted !== null && 'detail' in submitted ? submitted.detail : '';
  if (typeof detail === 'string' && detail) return detail.slice(0, 500);
  if (Array.isArray(detail)) {
    const messages = detail.filter(entry => typeof entry === 'object' && entry !== null && 'msg' in entry && typeof entry.msg === 'string')
      .slice(0, 3).map(entry => String(entry.msg).slice(0, 200));
    if (messages.length) return messages.join('; ');
  }
  return translate("schematic-api.check_component_values_wiring_and");
}

function failureReference(submitted: unknown): MessageReference | null {
  if (typeof submitted !== 'object' || submitted === null) return null;
  if ('message' in submitted) {
    const reference = parseMessage(submitted.message);
    if (reference) return reference;
  }
  if ('messages' in submitted && Array.isArray(submitted.messages)) {
    const references = submitted.messages.slice(0, 3).map(entry => parseMessage(entry)).filter(reference => reference !== null);
    return references.reduce<MessageReference | null>((first, second) => first
      ? { key: 'common.validation_details', values: { first, second } } : second, null);
  }
  return null;
}

export function analysisFailure(submitted: unknown): Error {
  const reference = failureReference(submitted);
  return reference ? new LocalizedFailure(reference.key, reference.values) : new Error(analysisFailureMessage(submitted));
}
