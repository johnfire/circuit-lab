import { engineering } from './schematic-model';
import { libraryPart } from './part-library';
import { boardOf } from './board-library';
import { passivePackage } from './footprint-options';
import type { AnalogReport, RatingCheck } from './schematic-types';

const RATING_LABELS: Record<string, string> = {
  if_max: 'Forward current', vr_max: 'Reverse voltage', iz_max: 'Zener current', pd_max: 'Power dissipation',
  vds_max: 'Drain–source voltage', vgs_max: 'Gate–source voltage', id_max: 'Drain current',
  vceo_max: 'Collector–emitter voltage', ic_max: 'Collector current', vs_max: 'Supply voltage', iout_max: 'Output current',
  vin_max: 'Input voltage', pin_current_max: 'Pin current', pin_voltage_max: 'Pin voltage',
  pin_negative_voltage_max: 'Voltage below ground', supply_current_max: 'Supply current',
  power_max: 'Power', voltage_max: 'Voltage', reverse_voltage_max: 'Reverse voltage (electrolytic)',
};

function RatingRow({ check }: { check: RatingCheck }) {
  const passive = passivePackage(check.device);
  const name = libraryPart(check.device)?.name ?? boardOf(check.device)?.name ?? (passive ? (check.device.startsWith('r_') ? 'Resistor, ' : 'Capacitor, ') + passive.note : check.device);
  const percent = check.limit > 0 ? Math.round(check.measured / check.limit * 100) : 0;
  return <article className={'check ' + (check.passed ? 'pass' : 'fail')}>
    <span aria-hidden="true">{check.passed ? '✓' : '×'}</span>
    <div><h3>{check.part} · {name} · {RATING_LABELS[check.rating] ?? check.rating} <small>{check.passed ? 'WITHIN LIMIT' : 'EXCEEDS LIMIT'}</small></h3>
      <p>{check.statistic === 'average' ? 'Average' : 'Peak'} {engineering(check.measured, check.unit)} of {engineering(check.limit, check.unit)} maximum ({percent}%).
        {check.trust === 'draft' && (passive ? ' Typical limit for this package; check the part you buy.' : ' Draft part: limit unconfirmed against the datasheet.')}</p></div>
  </article>;
}

export function AnalogRatings({ report }: { report: AnalogReport }) {
  const ratings = report.ratings ?? [];
  if (!ratings.length) return null;
  const failed = ratings.filter(check => !check.passed);
  const drafts = ratings.some(check => check.trust === 'draft');
  return <section className="editor-card" aria-labelledby="part-ratings-heading">
    <h2 id="part-ratings-heading">Part ratings <span className={'status-badge ' + (failed.length ? 'failed' : 'passed')}>
      {failed.length ? failed.length + ' of ' + ratings.length + ' exceeded' : 'All ' + ratings.length + ' within limits'}</span></h2>
    <p className="muted">Each part is checked against its absolute maximums across the whole run: peak voltage and current on every
      solver step, and time-averaged power. Resistors use their package's limits, capacitors their chosen voltage rating.{drafts && ' Draft parts are not yet reviewed against their datasheets, so a pass is not hardware approval.'}</p>
    {[...failed, ...ratings.filter(check => check.passed)].map(check => <RatingRow key={check.part + check.rating} check={check} />)}
  </section>;
}
