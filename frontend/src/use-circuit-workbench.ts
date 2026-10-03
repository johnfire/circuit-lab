import { useEffect, useState } from 'react';
import { fetchCircuits, requestSimulation } from './circuit-api';
import type { Circuit, SimulationReport } from './circuit-types';

function useCatalog() {
  const [circuits, setCircuits] = useState<Circuit[]>([]);
  const [loadError, setLoadError] = useState('');
  useEffect(() => {
    let isActive = true;
    void fetchCircuits().then(catalog => {
      if (isActive) setCircuits(catalog);
    }).catch(failure => {
      if (isActive) setLoadError(failure instanceof Error ? failure.message : 'Could not load circuit library.');
    });
    return () => { isActive = false; };
  }, []);
  return { circuits, loadError };
}

export function useCircuitWorkbench() {
  const { circuits, loadError } = useCatalog();
  const [selectedId, setSelectedId] = useState('');
  const selected = circuits.find(circuit => circuit.id === selectedId) ?? circuits[0] ?? null;
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const defaults = Object.fromEntries((selected?.parameters ?? []).map(parameter => [parameter.name, parameter.value]));
  const values = { ...defaults, ...overrides };
  const [rippleLimit, setRippleLimit] = useState(0.15);
  const [report, setReport] = useState<SimulationReport | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isStale, setIsStale] = useState(false);
  const [error, setError] = useState('');
  function selectCircuit(circuit: Circuit) {
    setSelectedId(circuit.id);
    setOverrides({});
    setReport(null);
    setIsStale(false);
    setError('');
  }
  const runSimulation = createRunHandler({ selected, values, rippleLimit, setIsRunning, setIsStale, setError, setReport });
  return { circuits, selected, values, rippleLimit, report, isRunning, isStale, error: error || loadError, selectCircuit,
    runSimulation, changeValue: (name: string, value: number) => {
      setOverrides(current => ({ ...current, [name]: value })); setIsStale(true);
    }, changeRipple: (value: number) => { setRippleLimit(value); setIsStale(true); } };
}

interface RunState {
  selected: Circuit | null;
  values: Record<string, number>;
  rippleLimit: number;
  setIsRunning: (value: boolean) => void;
  setIsStale: (value: boolean) => void;
  setError: (value: string) => void;
  setReport: (value: SimulationReport) => void;
}

function createRunHandler(state: RunState) {
  return async () => {
    if (!state.selected) return;
    state.setIsRunning(true);
    state.setIsStale(true);
    state.setError('');
    try {
      state.setReport(await requestSimulation(state.selected.id, state.values, state.rippleLimit));
      state.setIsStale(false);
    } catch (failure) {
      state.setError(failure instanceof Error ? failure.message : 'Simulation failed. Please retry.');
    } finally {
      state.setIsRunning(false);
    }
  };
}
