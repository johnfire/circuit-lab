import { useCallback, useEffect, useRef, useState } from 'react';
import { contentsFingerprint, parseSnapshot, projectRequest, revisionCommand, syncDecision } from './project-api';
import type { CircuitContents, CircuitSnapshot, ProjectSummary, RevisionSummary, SharingStatus } from './project-api';
import type { EditorState } from './use-schematic-editor';
import { synchronizeObservation } from './shared-observation';

interface CollaborationState {
  status: SharingStatus; projects: ProjectSummary[]; workspaces: ProjectSummary[]; saved: CircuitSnapshot | null;
  workspace: CircuitSnapshot | null; incoming: CircuitSnapshot | null; history: RevisionSummary[];
  message: string; busy: boolean; connected: boolean;
}
const INITIAL: CollaborationState = { status: { enabled: false, clients: [], endpoint: '' }, projects: [], workspaces: [],
  saved: null, workspace: null, incoming: null, history: [], message: 'Checking saved-circuit service…', busy: false, connected: false };

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
    catch (failure) { update({ message: failure instanceof Error ? failure.message : 'Saved circuits unavailable. Your draft stays local.' }); }
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
        if (!controller.signal.aborted) update({ status, projects, workspaces, message: status.enabled ? 'Private until you explicitly share.'
          : 'Saved circuits are not configured. Local editing and file export still work.' });
      } catch { if (!controller.signal.aborted) update({ message: 'Saved circuits unavailable. Local editing and file export still work.' }); }
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
    throw new Error('Save or synchronize your edits before running the shared revision.');
  }
  await projectRequest('/' + binding.document + '/runs', { revision: binding.revision, analysis: captured.editor.analysis,
    idempotency_key: crypto.randomUUID() });
  context.update({ message: 'Shared revision is running. Its result will appear only if the grid still matches.' });
}

async function saveCircuit(context: SharedContext, name: string, isNew: boolean) {
    const captured = context.latest.current, contents = editorContents(captured.editor);
    const saved = parseSnapshot(captured.state.saved && !isNew
      ? await projectRequest<CircuitSnapshot>('/' + captured.state.saved.document + '/replace', {
        ...revisionCommand(captured.state.saved, 'Saved browser circuit'), contents })
      : await projectRequest<CircuitSnapshot>('', { name, kind: 'project', contents, idempotency_key: crypto.randomUUID() }));
    context.update({ saved, projects: await projectRequest<ProjectSummary[]>(''), message: 'Project saved privately. Sharing requires your explicit choice.' });
}

async function openCircuit(context: SharedContext, document: string) {
    const { latest, update } = context;
    if (latest.current.state.workspace) throw new Error('Stop sharing before opening another saved project.');
    if (!window.confirm('Load this project onto the grid? Export your current draft first if you want to keep it.')) return;
    const captured = contentsFingerprint(editorContents(latest.current.editor));
    const saved = parseSnapshot(await projectRequest<CircuitSnapshot>('/' + document));
    adoptIfUnchanged(saved, captured, latest, update);
    update(saved.kind === 'workspace' ? { workspace: saved } : { saved });
}

async function shareCircuit(context: SharedContext, choice: { client: string; name: string; target: 'workspace' | 'project' }) {
    const { latest, update } = context, { client, name, target } = choice;
    const captured = latest.current, contents = editorContents(captured.editor);
    if (target === 'project' && !captured.state.saved) throw new Error('Save a private project first.');
    const shared = target === 'project' ? captured.state.saved! : captured.state.workspace
      ?? parseSnapshot(await projectRequest<CircuitSnapshot>('', { name: name.slice(0, 80), kind: 'workspace', contents, idempotency_key: crypto.randomUUID() }));
    if (target === 'workspace' && contentsFingerprint(contents) !== contentsFingerprint(shared.contents)) throw new Error('Wait for workspace synchronization before sharing.');
    await projectRequest('/' + shared.document + '/grants', { client, scopes: ['read', 'edit', 'simulate', 'view'], lifetime_minutes: 30 });
    const workspaces = await projectRequest<ProjectSummary[]>('?kind=workspace');
    update({ workspaces, ...(target === 'workspace' ? { workspace: shared, connected: true } : {}),
      message: 'Shared for 30 minutes. The chosen AI provider can receive this circuit; revocation cannot erase copies already received.' });
}

async function stopSharing(context: SharedContext) {
    const { latest, update } = context;
    const circuits = [latest.current.state.workspace, latest.current.state.saved].filter(snapshot => snapshot !== null);
    for (const shared of circuits) await projectRequest('/' + shared.document + '/stop-sharing', {});
    update({ workspace: null, connected: false, incoming: null, message: 'Sharing stopped for this circuit. The draft stays on your grid.' });
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
    if (!incoming || !window.confirm('Use the server revision? Export your unsent local draft first to keep it.')) return;
    latest.current.editor.applyRemote(incoming.contents.circuit, incoming.contents.sweep, incoming.actor);
    update({ workspace: incoming.kind === 'workspace' ? incoming : state.workspace,
      saved: incoming.kind === 'project' ? incoming : state.saved, incoming: null, message: 'Server revision loaded; history remains available.' });
}

type Latest = React.RefObject<{ editor: EditorState; state: CollaborationState }>;
type Update = (patch: Partial<CollaborationState>) => void;

function adoptIfUnchanged(snapshot: CircuitSnapshot, fingerprint: string, latest: Latest, update: Update) {
  if (contentsFingerprint(editorContents(latest.current.editor)) !== fingerprint || latest.current.editor.running) {
    update({ incoming: snapshot, message: 'The server changed while you edited locally. Your draft was kept; export it before choosing a revision.' });
    return;
  }
  latest.current.editor.applyRemote(snapshot.contents.circuit, snapshot.contents.sweep, snapshot.actor);
  update({ incoming: null, message: 'Acknowledged revision loaded from ' + snapshot.actor });
}

function useWorkspacePolling(workspace: string | undefined, latest: Latest, update: Update) {
  useEffect(() => {
    if (!workspace) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { await synchronizeWorkspace(workspace, latest, update, controller.signal); }
      catch (failure) { if (!controller.signal.aborted) update({ message: 'Unsent edits remain local. ' + (failure instanceof Error ? failure.message : 'Connection unavailable.') }); }
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
  if (decision === 'conflict') { update({ incoming: server, message: 'Revision conflict. Your unsent draft is preserved; choose the server revision or save your local work separately.' }); return; }
  if (decision === 'adopt') {
    adoptIfUnchanged(server, contentsFingerprint(editorContents(current.editor)), latest, update);
    update(server.kind === 'workspace' ? { workspace: server } : { saved: server });
  }
  if (decision === 'push' && binding.kind === 'workspace') {
    const acknowledged = parseSnapshot(await projectRequest<CircuitSnapshot>('/' + document + '/replace', {
      ...revisionCommand(binding, 'Synchronized browser draft'), contents: editorContents(current.editor) }, signal));
    if (!signal.aborted) update({ workspace: acknowledged, message: 'Browser edits acknowledged by the server.' });
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
