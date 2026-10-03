import { useRef, useState } from 'react';
import { simulateAnalog } from './schematic-api';
import { parseSchematic, readDraft, saveDraft } from './schematic-files';
import { addWire, makePart, starterCircuit } from './schematic-model';
import type { AnalogReport, EditorAction, Part, PartKind, Pin, Schematic } from './schematic-types';

function initialDraft(scope: string | null) {
  try { return { schematic: readDraft(scope) ?? starterCircuit(), error: scope ? '' : 'Account draft storage unavailable. Export a file to keep this circuit.' }; }
  catch { return { schematic: starterCircuit(), error: 'Browser draft unavailable. The RC example is loaded; export a file to keep your work.' }; }
}

async function executeSimulation(schematic: Schematic, callbacks: {
  running: (value: boolean) => void; error: (value: string) => void; report: (value: AnalogReport | null) => void;
}, audit: (action: string) => void) {
  callbacks.running(true); callbacks.error(''); callbacks.report(null);
  try { callbacks.report(await simulateAnalog(schematic)); audit('simulation.completed'); }
  catch (failure) { callbacks.error(failure instanceof Error ? failure.message : 'Simulation unavailable.'); }
  finally { callbacks.running(false); }
}

export function useSchematicEditor(scope: string | null) {
  const [initial] = useState(() => initialDraft(scope)), [schematic, setSchematic] = useState(initial.schematic);
  const [selected, setSelected] = useState<string | null>('R1');
  const [armed, setArmed] = useState<PartKind | null>(null);
  const [wireStart, setWireStart] = useState<Pin | null>(null);
  const [report, setReport] = useState<AnalogReport | null>(null);
  const [error, setError] = useState(initial.error);
  const [running, setRunning] = useState(false);
  const history = useRef<EditorAction[]>([]);
  const audit = (action: string) => { history.current.push({ timestamp: new Date().toISOString(),
    actor: 'user:browser', action, correlation_id: crypto.randomUUID(), outcome: 'success' }); };
  const commit = (next: Schematic, action: string, electrical = true) => {
    setSchematic(next); if (electrical) setReport(null); audit(action); setError('');
    try { saveDraft(next, scope); } catch { setError('Browser storage unavailable. Export your circuit before leaving.'); }
  };
  const attempt = (operation: () => void) => {
    try { operation(); } catch (failure) { setError(failure instanceof Error ? failure.message : 'Circuit edit failed.'); }
  };
  const update = (part: Part, electrical = true) => commit({ ...schematic,
    parts: schematic.parts.map(previous => previous.id === part.id ? part : previous) }, 'part.update:' + part.id, electrical);
  const place = (x: number, y: number) => attempt(() => {
    if (!armed || running) return;
    const part = makePart(armed, schematic.parts, x, y);
    commit({ ...schematic, parts: [...schematic.parts, part] }, 'part.add:' + part.id);
    setSelected(part.id); setArmed(null);
  });
  const connect = (pin: Pin) => attempt(() => {
    if (running) return;
    if (!wireStart) { setWireStart(pin); setArmed(null); return; }
    commit(addWire(schematic, wireStart, pin), 'wire.add'); setWireStart(null);
  });
  const run = () => { setWireStart(null); setArmed(null); return executeSimulation(schematic,
    { running: setRunning, error: setError, report: setReport }, audit); };
  return { schematic, selected, armed, wireStart, report, error, running, history, setSelected, setError,
    setArmed, setWireStart, commit, update, place, connect, run,
    importText: (text: string) => attempt(() => { commit(parseSchematic(text), 'circuit.import'); setSelected(null); setWireStart(null); }),
    remove: (id: string) => { commit({ ...schematic, parts: schematic.parts.filter(part => part.id !== id),
      wires: schematic.wires.filter(wire => wire.a.part !== id && wire.b.part !== id) }, 'part.remove:' + id); setSelected(null); setWireStart(null); },
  };
}

export type EditorState = ReturnType<typeof useSchematicEditor>;
