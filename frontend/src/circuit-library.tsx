import { translate } from './localization.ts';
import type { Circuit } from './circuit-types';

interface Props { circuits: Circuit[]; selectedId?: string; isRunning: boolean; onSelect: (circuit: Circuit) => void }

export function CircuitLibrary({ circuits, selectedId, isRunning, onSelect }: Props) {
  return <aside className="library" aria-label={translate("circuit-library.circuit_library")}>
    <span className="small-label">{translate("circuit-library.the_bench")}</span><h2>{translate("circuit-library.circuit_library")}</h2>
    <p>{translate("circuit-library.nine_starting_points")}<br />{translate("circuit-library.an_open_invitation_to_experiment")}</p>
    {['analog', 'digital'].map(category => <section key={category}>
      <h3>{translate(category === 'digital' ? 'common.digital' : 'common.analogue')} <span>{circuits.filter(circuit => circuit.category === category).length}</span></h3>
      {circuits.filter(circuit => circuit.category === category).map(circuit => <button key={circuit.id}
        className={selectedId === circuit.id ? 'circuit-choice selected' : 'circuit-choice'}
        aria-pressed={selectedId === circuit.id} disabled={isRunning} onClick={() => onSelect(circuit)}>
        <span aria-hidden="true">{category === 'analog' ? '∿' : '⊓'}</span>{circuit.title}
        <span className="choice-arrow" aria-hidden="true">↗</span></button>)}
    </section>)}
    <div className="library-footer">{translate("circuit-library.measure_understand_refine")}<br /><span>{translate("circuit-library.simulation_is_the_beginning")}</span></div>
  </aside>;
}
