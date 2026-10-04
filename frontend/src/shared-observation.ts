import { contentsFingerprint, projectRequest } from './project-api';
import type { CircuitContents, CircuitSnapshot } from './project-api';
import type { EditorState } from './use-schematic-editor';
import type { ObservationReport, Pin } from './schematic-types';

interface StoredRun { id: string; revision: string; status: string }
interface StoredReport { status: string; revision: string; report: ObservationReport | null }
interface PendingView { id: string; command: { revision: string; pins: Pin[]; time: number | null; frequency: number | null } }

/** Never label evidence from a different revision as readings of the local grid. */
export async function synchronizeObservation(binding: CircuitSnapshot, current: () => EditorState, signal: AbortSignal) {
  const contents = (): CircuitContents => ({ circuit: current().schematic, sweep: current().persistedSweep });
  const clean = () => !signal.aborted && !current().running && contentsFingerprint(contents()) === contentsFingerprint(binding.contents);
  if (!clean()) return;
  const runs = await projectRequest<StoredRun[]>('/' + binding.document + '/runs', undefined, signal);
  const latest = runs.find(run => run.revision === binding.revision && run.status === 'completed');
  if (latest) {
    const saved = await projectRequest<StoredReport>('/' + binding.document + '/runs/' + latest.id, undefined, signal);
    if (clean() && saved.status === 'completed' && saved.revision === binding.revision && saved.report
      && saved.report.correlation_id !== current().report?.correlation_id && saved.report.correlation_id !== current().acReport?.correlation_id) {
      current().receiveReport(saved.report);
    }
  }
  if (binding.kind !== 'workspace' || !clean()) return;
  const pending = await projectRequest<PendingView | null>('/' + binding.document + '/view', undefined, signal);
  if (pending && clean() && pending.command.revision === binding.revision && current().remoteView?.id !== pending.id) {
    if (pending.command.frequency !== null && current().acReport) current().setAnalysis('ac');
    if (pending.command.time !== null && current().report) current().setAnalysis('transient');
    current().receiveView({ ...pending.command, id: pending.id, document: binding.document });
  }
}
