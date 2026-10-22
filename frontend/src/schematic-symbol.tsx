import { libraryPart } from './part-library';
import type { Part } from './schematic-types';

function DiodeSymbol({ category }: { category: string | undefined }) {
  const bar = category === 'zener' ? 'M8 -20 L14 -14 V14 L20 20'
    : category === 'schottky' ? 'M20 -10 V-14 H14 V14 H8 V10' : 'M14 -14 V14';
  return <g>
    <path d="M-64 0 H-14 M14 0 H64" />
    <path className="symbol-fill" d="M-14 -14 L-14 14 L14 0 Z" />
    <path d={bar} />
    {category === 'led' && <path d="M0 -20 L12 -34 M6 -34 H12 V-28 M10 -16 L22 -30 M16 -30 H22 V-24" />}
  </g>;
}

function MosfetSymbol({ channel }: { channel: 'n' | 'p' }) {
  const arrow = channel === 'n' ? 'M12 -6 L0 0 L12 6' : 'M0 -6 L12 0 L0 6';
  return <g>
    <path d="M-64 0 H-18 M-18 -20 V20" />
    <path d="M-6 -26 V-12 M-6 -6 V6 M-6 12 V26" />
    <path d="M-6 -19 H32 V-64 M-6 19 H32 V64 M-6 0 H32 V19" />
    <path className="symbol-fill" d={arrow} />
  </g>;
}

function BjtSymbol({ polarity }: { polarity: 'npn' | 'pnp' }) {
  const arrow = polarity === 'npn' ? 'M14 30 L26 30 L20 20 Z' : 'M2 14 L14 14 L6 24 Z';
  return <g>
    <circle r="34" cx="8" />
    <path d="M-64 0 H-10 M-10 -22 V22" />
    <path d="M-10 -10 L32 -34 V-64 M-10 10 L32 34 V64" />
    <path className="symbol-fill" d={arrow} />
  </g>;
}

export function SchematicSymbol({ part }: { part: Part }) {
  const { kind } = part;
  if (kind === 'GND') return <g><path d="M0 -64 V0 M-22 0 H22 M-15 9 H15 M-7 18 H7" /></g>;
  if (kind === 'D') return <DiodeSymbol category={libraryPart(part.device)?.category} />;
  if (kind === 'NMOS' || kind === 'PMOS') return <MosfetSymbol channel={kind === 'NMOS' ? 'n' : 'p'} />;
  if (kind === 'NPN' || kind === 'PNP') return <BjtSymbol polarity={kind === 'NPN' ? 'npn' : 'pnp'} />;
  return <g>
    <path d="M-64 0 H-32 M32 0 H64" />
    {kind === 'R' && <path d="M-32 0 L-26 -12 L-16 12 L-6 -12 L4 12 L14 -12 L24 12 L32 0" />}
    {kind === 'C' && <path d="M-32 0 H-7 M-7 -24 V24 M7 -24 V24 M7 0 H32" />}
    {kind === 'L' && <path d="M-32 0 C-32 -24 -16 -24 -16 0 C-16 -24 0 -24 0 0 C0 -24 16 -24 16 0 C16 -24 32 -24 32 0" />}
    {(kind === 'V' || kind === 'PULSE' || kind === 'SIN') && <><circle r="32" />
      {kind === 'V' ? <path d="M-22 0 H-10 M-16 -6 V6 M10 0 H22" />
        : kind === 'SIN' ? <path d="M-23 0 C-16 -23 -7 -23 0 0 C7 23 16 23 23 0" />
          : <path d="M-23 10 H-12 V-10 H8 V10 H23" />}</>}
  </g>;
}
