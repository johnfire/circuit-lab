import { RATING_LABELS } from './rating-labels.ts';
import { translate } from './localization.ts';
import { engineering } from './schematic-model';
import { libraryPart } from './part-library';
import { boardOf } from './board-library';
import { passivePackage } from './footprint-options';
import type { AnalogReport, RatingCheck } from './schematic-types';



function RatingRow({ check }: { check: RatingCheck }) {
  const passive = passivePackage(check.device);
  const name = libraryPart(check.device)?.name ?? boardOf(check.device)?.name ?? (passive ? (check.device.startsWith('r_') ? translate("analog-ratings.resistor") : translate("analog-ratings.capacitor")) + passive.note : check.device);
  const percent = check.limit > 0 ? Math.round(check.measured / check.limit * 100) : 0;
  return <article className={'check ' + (check.passed ? 'pass' : 'fail')}>
    <span aria-hidden="true">{check.passed ? '✓' : '×'}</span>
    <div><h3>{check.part} · {name} · {RATING_LABELS[check.rating] ?? check.rating} <small>{check.passed ? translate("analog-ratings.within_limit") : translate("analog-ratings.exceeds_limit")}</small></h3>
      <p>{translate('ratings.measurement', { statistic: translate(check.statistic === 'average' ? 'analog-ratings.average' : 'analog-ratings.peak'), measured: engineering(check.measured, check.unit), limit: engineering(check.limit, check.unit), percent })}
        {check.trust === 'draft' && (passive ? translate("analog-ratings.typical_limit_for_this_package") : translate("analog-ratings.draft_part_limit_unconfirmed_against"))}</p></div>
  </article>;
}

export function AnalogRatings({ report }: { report: AnalogReport }) {
  const ratings = report.ratings ?? [];
  if (!ratings.length) return null;
  const failed = ratings.filter(check => !check.passed);
  const drafts = ratings.some(check => check.trust === 'draft');
  return <section className="editor-card" aria-labelledby="part-ratings-heading">
    <h2 id="part-ratings-heading">{translate("analog-ratings.part_ratings")}<span className={'status-badge ' + (failed.length ? 'failed' : 'passed')}>
      {failed.length ? translate('ratings.summary_failed', { count: failed.length, total: ratings.length }) : translate('ratings.summary_passed', { count: ratings.length })}</span></h2>
    <p className="muted">{translate("analog-ratings.each_part_is_checked_against")}{drafts && translate("analog-ratings.draft_parts_are_not_yet")}</p>
    {[...failed, ...ratings.filter(check => check.passed)].map(check => <RatingRow key={check.part + check.rating} check={check} />)}
  </section>;
}
