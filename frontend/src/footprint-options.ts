import genericFootprints from '../../circuits/footprints.json' with { type: 'json' };
import { libraryPart } from './part-library.ts';
import type { Part } from './schematic-types';

export interface FootprintOption { id: string; mount: 'tht' | 'smd'; kicad: string; note: string; lcsc?: string | null }

const GENERIC = genericFootprints as unknown as Record<string, FootprintOption[]>;

/** PCB package choices for a placed part: generic for R/C/L, the part's own for library devices. */
export function footprintOptions(part: Part): FootprintOption[] {
  return GENERIC[part.kind] ?? libraryPart(part.device)?.footprints ?? [];
}

/** "TO-220-3_Vertical (through-hole)": the KiCad footprint name without its library. */
export function footprintLabel(option: FootprintOption): string {
  return option.kicad.split(':')[1] + (option.mount === 'tht' ? ' (through-hole)' : ' (SMD)');
}
