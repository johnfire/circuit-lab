import type { PartKind } from './schematic-types';

export function SchematicSymbol({ kind }: { kind: PartKind }) {
  if (kind === 'GND') return <g><path d="M0 -64 V0 M-22 0 H22 M-15 9 H15 M-7 18 H7" /></g>;
  return <g>
    <path d="M-64 0 H-32 M32 0 H64" />
    {kind === 'R' && <path d="M-32 0 L-26 -12 L-16 12 L-6 -12 L4 12 L14 -12 L24 12 L32 0" />}
    {kind === 'C' && <path d="M-32 0 H-7 M-7 -24 V24 M7 -24 V24 M7 0 H32" />}
    {kind === 'L' && <path d="M-32 0 C-32 -24 -16 -24 -16 0 C-16 -24 0 -24 0 0 C0 -24 16 -24 16 0 C16 -24 32 -24 32 0" />}
    {(kind === 'V' || kind === 'PULSE') && <><circle r="32" />
      {kind === 'V' ? <path d="M-22 0 H-10 M-16 -6 V6 M10 0 H22" />
        : <path d="M-23 10 H-12 V-10 H8 V10 H23" />}</>}
  </g>;
}
