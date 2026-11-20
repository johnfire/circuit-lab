import type { DisplayMessage } from './display-message.ts';
import { message, LocalizedFailure, failureMessage } from './display-message.ts';
import { translate } from './localization.ts';
import { useCallback, useEffect, useRef, useState } from 'react';
import { contentsFingerprint, parseSnapshot, projectRequest, revisionCommand, syncDecision } from './project-api';
import type { CircuitContents, CircuitSnapshot, ProjectSummary, RevisionSummary, SharingStatus } from './project-api';
import type { EditorState } from './use-schematic-editor';
import { synchronizeObservation } from './shared-observation';

interface CollaborationState {
  status: SharingStatus; projects: ProjectSummary[]; workspaces: ProjectSummary[]; saved: CircuitSnapshot | null;
  workspace: CircuitSnapshot | null; incoming: CircuitSnapshot | null; history: RevisionSummary[];
  message: DisplayMessage; busy: boolean; connected: boolean;
}
const INITIAL: CollaborationState = { status: { enabled: false, clients: [], endpoint: '' }, projects: [], workspaces: [],
  saved: null, workspace: null, incoming: null, history: [], message: message("shared-circuit.checking_savedcircuit_service"), busy: false, connected: false };

function editorContents(editor: EditorState): CircuitContents { return { circuit: editor.schematic, sweep: editor.persistedSweep }; }

export function useSharedCircuit(editor: EditorState) {
  const [state, setState] = useState(INITIAL);
  const latest = useRef({ editor, state });
  useEffect(() => { latest.current = { editor, state }; }, [editor, state]);
  const update = useCallback((patch: Partial<CollaborationState>) => setState(previous => ({ ...previous, ...patch })), []);
  const attempt = async (operation: () => Promise<void>) => {
    if (latest.current.state.busy) return;
    update({ busy: true });
    try { await operation(); }
    catch (failure) { update({ message: failure instanceof Error ? failureMessage(failure) : message("shared-circuit.saved_circuits_unavailable_your_draft") }); }
    finally { update({ busy: false }); }
  };
  useInitialStatus(update);
  useWorkspacePolling(state.workspace?.document ?? state.saved?.document, latest, update);
  return { ...state, ...sharingActions({ latest, update, attempt }) };
}

function useInitialStatus(update: Update) {
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const status = await projectRequest<SharingStatus>('/status', undefined, controller.signal);
        const projects = status.enabled ? await projectRequest<ProjectSummary[]>('', undefined, controller.signal) : [];
        const workspaces = status.enabled ? await projectRequest<ProjectSummary[]>('?kind=workspace', undefined, controller.signal) : [];
        if (!controller.signal.aborted) update({ status, projects, workspaces, message: status.enabled ? message("shared-circuit.private_until_you_explicitly_share")
          : message("shared-circuit.saved_circuits_are_not_configured") });
      } catch { if (!controller.signal.aborted) update({ message: message("shared-circuit.saved_circuits_unavailable_local_editing") }); }
    };
    void load();
    return () => controller.abort();
  }, [update]);
}

interface SharedContext { latest: Latest; update: Update; attempt: (operation: () => Promise<void>) => Promise<void> }

function sharingActions(context: SharedContext) {
  return {
    save: (name: string, isNew = false) => context.attempt(() => saveCircuit(context, name, isNew)),
    open: (document: string) => context.attempt(() => openCircuit(context, document)),
    share: (client: string, name: string, target: 'workspace' | 'project') => context.attempt(() => shareCircuit(context, { client, name, target })),
    stop: () => context.attempt(() => stopSharing(context)),
    undo: () => context.attempt(() => undoCircuit(context)),
    simulate: () => context.attempt(() => simulateShared(context)),
    acceptIncoming: () => acceptIncoming(context),
  };
}

async function simulateShared(context: SharedContext) {
  const captured = context.latest.current, binding = captured.state.workspace ?? captured.state.saved;
  if (!binding || contentsFingerprint(editorContents(captured.editor)) !== contentsFingerprint(binding.contents)) {
    throw new LocalizedFailure("shared-circuit.save_or_synchronize_your_edits");
  }
  await projectRequest('/' + binding.document + '/runs', { revision: binding.revision, analysis: captured.editor.analysis,
    idempotency_key: crypto.randomUUID() });
  context.update({ message: message("shared-circuit.shared_revision_is_running_its") });
}

async function saveCircuit(context: SharedContext, name: string, isNew: boolean) {
    const captured = context.latest.current, contents = editorContents(captured.editor);
    const saved = parseSnapshot(captured.state.saved && !isNew
      ? await projectRequest<CircuitSnapshot>('/' + captured.state.saved.document + '/replace', {
        ...revisionCommand(captured.state.saved, 'Saved browser circuit'), contents })
      : await projectRequest<CircuitSnapshot>('', { name, kind: 'project', contents, idempotency_key: crypto.randomUUID() }));
    context.update({ saved, projects: await projectRequest<ProjectSummary[]>(''), message: message("shared-circuit.project_saved_privately_sharing_requires") });
}

async function openCircuit(context: SharedContext, document: string) {
    const { latest, update } = context;
    if (latest.current.state.workspace) throw new LocalizedFailure("shared-circuit.stop_sharing_before_opening_another");
    if (!window.confirm(translate("shared-circuit.load_this_project_onto_the"))) return;
    const captured = contentsFingerprint(editorContents(latest.current.editor));
    const saved = parseSnapshot(await projectRequest<CircuitSnapshot>('/' + document));
    adoptIfUnchanged(saved, captured, latest, update);
    update(saved.kind === 'workspace' ? { workspace: saved } : { saved });
}

async function shareCircuit(context: SharedContext, choice: { client: string; name: string; target: 'workspace' | 'project' }) {
    const { latest, update } = context, { client, name, target } = choice;
    const captured = latest.current, contents = editorContents(captured.editor);
    if (target === 'project' && !captured.state.saved) throw new LocalizedFailure("shared-circuit.save_a_private_project_first");
    const shared = target === 'project' ? captured.state.saved! : captured.state.workspace
      ?? parseSnapshot(await projectRequest<CircuitSnapshot>('', { name: name.slice(0, 80), kind: 'workspace', contents, idempotency_key: crypto.randomUUID() }));
    if (target === 'workspace' && contentsFingerprint(contents) !== contentsFingerprint(shared.contents)) throw new LocalizedFailure("shared-circuit.wait_for_workspace_synchronization_before");
    await projectRequest('/' + shared.document + '/grants', { client, scopes: ['read', 'edit', 'simulate', 'view'], lifetime_minutes: 30 });
    const workspaces = await projectRequest<ProjectSummary[]>('?kind=workspace');
    update({ workspaces, ...(target === 'workspace' ? { workspace: shared, connected: true } : {}),
      message: message("shared-circuit.shared_for_30_minutes_the") });
}

async function stopSharing(context: SharedContext) {
    const { latest, update } = context;
    const circuits = [latest.current.state.workspace, latest.current.state.saved].filter(snapshot => snapshot !== null);
    for (const shared of circuits) await projectRequest('/' + shared.document + '/stop-sharing', {});
    update({ workspace: null, connected: false, incoming: null, message: message("shared-circuit.sharing_stopped_for_this_circuit") });
}

async function undoCircuit(context: SharedContext) {
    const { latest, update } = context;
    const captured = latest.current, shared = captured.state.workspace ?? captured.state.saved;
    if (!shared) return;
    const fingerprint = contentsFingerprint(editorContents(captured.editor));
    const restored = parseSnapshot(await projectRequest<CircuitSnapshot>('/' + shared.document + '/undo', revisionCommand(shared, 'Undo last change')));
    adoptIfUnchanged(restored, fingerprint, latest, update);
    update(captured.state.workspace ? { workspace: restored } : { saved: restored });
}

function acceptIncoming(context: SharedContext) {
    const { latest, update } = context;
    const state = latest.current.state;
    const incoming = latest.current.state.incoming;
    if (!incoming || !window.confirm(translate("shared-circuit.use_the_server_revision_export"))) return;
    latest.current.editor.applyRemote(incoming.contents.circuit, incoming.contents.sweep, incoming.actor);
    update({ workspace: incoming.kind === 'workspace' ? incoming : state.workspace,
      saved: incoming.kind === 'project' ? incoming : state.saved, incoming: null, message: message("shared-circuit.server_revision_loaded_history_remains") });
}

type Latest = React.RefObject<{ editor: EditorState; state: CollaborationState }>;
type Update = (patch: Partial<CollaborationState>) => void;

function adoptIfUnchanged(snapshot: CircuitSnapshot, fingerprint: string, latest: Latest, update: Update) {
  if (contentsFingerprint(editorContents(latest.current.editor)) !== fingerprint || latest.current.editor.running) {
    update({ incoming: snapshot, message: message("shared-circuit.the_server_changed_while_you") });
    return;
  }
  latest.current.editor.applyRemote(snapshot.contents.circuit, snapshot.contents.sweep, snapshot.actor);
  update({ incoming: null, message: message("shared-circuit.acknowledged_revision_loaded_from", { actor: snapshot.actor }) });
}

function useWorkspacePolling(workspace: string | undefined, latest: Latest, update: Update) {
  useEffect(() => {
    if (!workspace) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { await synchronizeWorkspace(workspace, latest, update, controller.signal); }
      catch (failure) { if (!controller.signal.aborted) update({ message: message("shared-circuit.unsent_edits_remain_local", { reason: failure instanceof Error ? failureMessage(failure) : message("shared-circuit.connection_unavailable") }) }); }
      if (!controller.signal.aborted) timer = setTimeout(() => { void poll(); }, 1500);
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [workspace, latest, update]);
}

async function synchronizeWorkspace(document: string, latest: Latest, update: Update, signal: AbortSignal) {
  const captured = latest.current, binding = captured.state.workspace ?? captured.state.saved;
  if (!binding || captured.state.busy || captured.state.incoming) return;
  const server = parseSnapshot(await projectRequest<CircuitSnapshot>('/' + document, undefined, signal));
  const current = latest.current;
  const currentBinding = current.state.workspace ?? current.state.saved;
  if (signal.aborted || currentBinding?.document !== document || currentBinding.revision !== binding.revision) return;
  const decision = syncDecision(binding, editorContents(current.editor), server, current.editor.running);
  if (decision === 'conflict') { update({ incoming: server, message: message("shared-circuit.revision_conflict_your_unsent_draft") }); return; }
  if (decision === 'adopt') {
    adoptIfUnchanged(server, contentsFingerprint(editorContents(current.editor)), latest, update);
    update(server.kind === 'workspace' ? { workspace: server } : { saved: server });
  }
  if (decision === 'push' && binding.kind === 'workspace') {
    const acknowledged = parseSnapshot(await projectRequest<CircuitSnapshot>('/' + document + '/replace', {
      ...revisionCommand(binding, 'Synchronized browser draft'), contents: editorContents(current.editor) }, signal));
    if (!signal.aborted) update({ workspace: acknowledged, message: message("shared-circuit.browser_edits_acknowledged_by_the") });
  }
  await synchronizeMetadata(document, latest, update, signal);
  if (decision === 'none') await synchronizeObservation(binding, () => latest.current.editor, signal);
}

async function synchronizeMetadata(document: string, latest: Latest, update: Update, signal: AbortSignal) {
  const history = await projectRequest<RevisionSummary[]>('/' + document + '/history', undefined, signal);
  const grants = await projectRequest<{ expires_at: string; revoked_at: string | null }[]>('/' + document + '/grants', undefined, signal);
  if (!signal.aborted && (latest.current.state.workspace ?? latest.current.state.saved)?.document === document) {
    update({ history, connected: grants.some(grant => !grant.revoked_at && Date.parse(grant.expires_at) > Date.now()) });
  }
}
