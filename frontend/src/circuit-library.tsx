import type { Circuit } from './circuit-types';

interface Props { circuits: Circuit[]; selectedId?: string; isRunning: boolean; onSelect: (circuit: Circuit) => void }

export function CircuitLibrary({ circuits, selectedId, isRunning, onSelect }: Props) {
  return <aside className="library" aria-label="Circuit library">
    <span className="small-label">THE BENCH</span><h2>Circuit library</h2>
    <p>Nine starting points.<br />An open invitation to experiment.</p>
    {['analog', 'digital'].map(category => <section key={category}>
      <h3>{category} <span>{circuits.filter(circuit => circuit.category === category).length}</span></h3>
      {circuits.filter(circuit => circuit.category === category).map(circuit => <button key={circuit.id}
        className={selectedId === circuit.id ? 'circuit-choice selected' : 'circuit-choice'}
        aria-pressed={selectedId === circuit.id} disabled={isRunning} onClick={() => onSelect(circuit)}>
        <span aria-hidden="true">{category === 'analog' ? '∿' : '⊓'}</span>{circuit.title}
        <span className="choice-arrow" aria-hidden="true">↗</span></button>)}
    </section>)}
    <div className="library-footer">Measure. Understand. Refine.<br /><span>Simulation is the beginning.</span></div>
  </aside>;
}
