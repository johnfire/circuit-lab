import { useRef, useState } from 'react';
import { useAnalogAnalysis } from './use-analog-analysis';
import { useRemoteObservation } from './use-remote-observation';
import { parseSchematic, readDraft, saveDraft } from './schematic-files';
import { addWire, makePart, starterCircuit } from './schematic-model';
import type { EditorAction, Part, PartKind, Pin, Schematic, Sweep } from './schematic-types';

function initialDraft(scope: string | null) {
  try { return { schematic: readDraft(scope) ?? starterCircuit(), error: scope ? '' : 'Account draft storage unavailable. Export a file to keep this circuit.' }; }
  catch { return { schematic: starterCircuit(), error: 'Browser draft unavailable. The RC example is loaded; export a file to keep your work.' }; }
}

export function useSchematicEditor(scope: string | null) {
  const { initial, schematic, setSchematic } = useInitialCircuit(scope);
  const [selected, setSelected] = useState<string | null>('R1');
  const [armed, setArmed] = useState<PartKind | null>(null);
  const [wireStart, setWireStart] = useState<Pin | null>(null);
  const { hasStoredSweep, setHasStoredSweep, updateSweep } = useStoredSweep();
  const simulation = useAnalogAnalysis(schematic, initial.error);
  const observation = useRemoteObservation();
  const { running, setError } = simulation;
  const { history, audit } = useEditorHistory();
  const commit = (next: Schematic, action: string, electrical = true) => {
    if (running) return;
    setSchematic(next); observation.receiveView(null); if (electrical) simulation.invalidate(action === 'timing.update' ? 'transient' : 'both'); audit(action); setError('');
    try { saveDraft(next, scope); } catch { setError('Browser storage unavailable. Export your circuit before leaving.'); }
  };
  const attempt = guardedEditorOperation(setError);
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
  const run = () => runAnalysis(simulation, hasStoredSweep, audit, () => { setWireStart(null); setArmed(null); });
  const applyRemote = remoteSnapshotReceiver({ running, setSchematic, simulation, history, scope, setWireStart, setArmed, setHasStoredSweep, clearView: () => observation.receiveView(null) });
  return { ...simulation, ...observation, schematic, selected, armed, wireStart, history, setSelected,
    persistedSweep: hasStoredSweep ? simulation.sweep : null,
    updateSweep: (next: Sweep) => updateSweep(simulation, next, audit),
    setArmed, setWireStart, commit, update, place, connect, run, applyRemote,
    importText: (text: string) => attempt(() => { commit(parseSchematic(text), 'circuit.import'); setSelected(null); setWireStart(null); }),
    remove: (id: string) => { commit({ ...schematic, parts: schematic.parts.filter(part => part.id !== id),
      wires: schematic.wires.filter(wire => wire.a.part !== id && wire.b.part !== id) }, 'part.remove:' + id); setSelected(null); setWireStart(null); },
  };
}

export type EditorState = ReturnType<typeof useSchematicEditor>;

function useInitialCircuit(scope: string | null) {
  const [initial] = useState(() => initialDraft(scope));
  const [schematic, setSchematic] = useState(initial.schematic);
  return { initial, schematic, setSchematic };
}

function useStoredSweep() {
  const [hasStoredSweep, setHasStoredSweep] = useState(true);
  const updateSweep = (simulation: ReturnType<typeof useAnalogAnalysis>, next: Sweep, audit: (action: string) => void) => {
    if (simulation.running) return;
    setHasStoredSweep(true); simulation.updateSweep(next); audit('sweep.update');
  };
  return { hasStoredSweep, setHasStoredSweep, updateSweep };
}

function guardedEditorOperation(setError: (message: string) => void) {
  return (operation: () => void) => {
    try { operation(); } catch (failure) { setError(failure instanceof Error ? failure.message : 'Circuit edit failed.'); }
  };
}

function useEditorHistory() {
  const history = useRef<EditorAction[]>([]);
  const audit = (action: string, correlation?: string) => { history.current.push({ timestamp: new Date().toISOString(),
    actor: 'user:browser', action, correlation_id: correlation ?? crypto.randomUUID(), outcome: action.endsWith('.failed') ? 'failure' : 'success' }); };
  return { history, audit };
}

interface RemoteContext {
  running: boolean; setSchematic: (next: Schematic) => void; simulation: ReturnType<typeof useAnalogAnalysis>;
  history: React.RefObject<EditorAction[]>; scope: string | null;
  setWireStart: (pin: Pin | null) => void; setArmed: (kind: PartKind | null) => void;
  setHasStoredSweep: (hasSweep: boolean) => void;
  clearView: () => void;
}

function remoteSnapshotReceiver(context: RemoteContext) {
  return (next: Schematic, sweep: Sweep | null, actor: string) => {
    if (context.running) return;
    context.setSchematic(next); context.simulation.invalidate('both');
    context.clearView();
    context.setHasStoredSweep(sweep !== null);
    if (sweep) context.simulation.updateSweep(sweep);
    context.setWireStart(null); context.setArmed(null);
    context.history.current.push({ timestamp: new Date().toISOString(), actor, action: 'collaboration.received',
      correlation_id: crypto.randomUUID(), outcome: 'success' });
    try { saveDraft(next, context.scope); }
    catch { context.simulation.setError('Server revision loaded, but browser storage failed. Export a file.'); }
  };
}

function runAnalysis(simulation: ReturnType<typeof useAnalogAnalysis>, hasStoredSweep: boolean,
  audit: (action: string, correlation?: string) => void, clearTools: () => void) {
  clearTools();
  if (!hasStoredSweep && simulation.analysis === 'ac') {
    simulation.setError('Set an AC excitation before running this revision.'); return;
  }
  return simulation.run(audit);
}
