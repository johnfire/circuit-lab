import { translate } from './localization.ts';
import type { Circuit } from './circuit-types';

interface Props {
  circuit: Circuit;
  values: Record<string, number>;
  rippleLimit: number;
  isRunning: boolean;
  onChange: (name: string, value: number) => void;
  onRippleChange: (value: number) => void;
  onRun: () => void;
  onReset: () => void;
}

export function ParameterPanel(props: Props) {
  return <section className="parameter-panel" aria-labelledby="parameters-heading">
    <div className="section-heading"><h2 id="parameters-heading">{translate("parameter-panel.design_parameters")}</h2>
      <button className="text-button" onClick={props.onReset} disabled={props.isRunning}>{translate("parameter-panel.reset")}</button></div>
    <p className="muted">{translate("parameter-panel.adjust_the_values_let_the")}</p>
    <form onSubmit={event => { event.preventDefault(); props.onRun(); }}>
      {props.circuit.parameters.map(parameter => <div className="parameter" key={parameter.name}>
        <label htmlFor={'parameter-' + parameter.name}>{parameter.name}
          <span>{parameter.unit === 'Ω' ? translate("parameter-panel.resistance") : translate("parameter-panel.capacitance")}</span></label>
        <div className="input-unit">
          <input id={'parameter-' + parameter.name} type="number" required step="any"
            min={parameter.minimum} max={parameter.maximum}
            value={Number.isFinite(props.values[parameter.name]) ? props.values[parameter.name] : ''}
            disabled={props.isRunning}
            onChange={event => props.onChange(parameter.name, event.target.valueAsNumber)} />
          <span>{parameter.unit}</span>
        </div>
      </div>)}
      {props.circuit.parameters.length === 0 && <p>{translate("parameter-panel.this_example_has_fixed_logic")}</p>}
      {props.circuit.id === 'rc_lowpass' && <div className="parameter">
        <label htmlFor="ripple-target">{translate("parameter-panel.ripple_target")}<span>{translate("parameter-panel.peaktopeak")}</span></label>
        <div className="input-unit"><input id="ripple-target" type="number" step="any" min="0.001"
          max="24" required value={Number.isFinite(props.rippleLimit) ? props.rippleLimit : ''}
          disabled={props.isRunning}
          onChange={event => props.onRippleChange(event.target.valueAsNumber)} /><span>V</span></div>
      </div>}
      <button className="run-button" type="submit" disabled={props.isRunning}>
        {props.isRunning ? translate('common.simulating') : translate("parameter-panel.run_simulation")}<span aria-hidden="true">↗</span>
      </button>
    </form>
    <div className="model-note"><span className="small-label">{translate("parameter-panel.model_trust")}</span>
      <strong>{translate("parameter-panel.generic_ideal")}</strong>
      <p>{translate("parameter-panel.results_describe_this_model_real")}</p></div>
  </section>;
}
