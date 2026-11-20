import type { DisplayMessage } from './display-message.ts';
import { message } from './display-message.ts';
import { useState } from 'react';
import { defaultProbes, probeKey } from './observation-signals';
import type { Pin, Probe, Schematic } from './schematic-types';

export function useObservationProbes(schematic: Schematic) {
  const [probes, setProbes] = useState<Probe[]>(() => defaultProbes(schematic));
  const [tool, setTool] = useState<Probe['kind']>('node');
  const [first, setFirst] = useState<Pin | null>(null);
  const [notice, setMessage] = useState<DisplayMessage>('');
  const add = (probe: Probe) => {
    setProbes(previous => previous.some(existing => probeKey(existing) === probeKey(probe)) ? previous
      : previous.length < 8 ? [...previous, probe] : previous);
    setMessage(message("observation-probes.probe_pinned_up_to_eight"));
  };
  const pin = (selected: Pin) => {
    if (tool === 'node') add({ kind: 'node', pin: selected });
    if (tool === 'differential') {
      if (first) { add({ kind: 'differential', first, second: selected }); setFirst(null); }
      else { setFirst(selected); setMessage(message("observation-probes.choose_the_second_terminal_for")); }
    }
    if (tool === 'current') add({ kind: 'current', part: selected.part });
  };
  return { probes, tool, first, message: notice, pin, add, setMessage, replace: (next: Probe[]) => setProbes(next.slice(0, 8)),
    chooseTool: (next: Probe['kind']) => { setTool(next); setFirst(null); },
    remove: (probe: Probe) => setProbes(previous => previous.filter(existing => probeKey(existing) !== probeKey(probe))) };
}
