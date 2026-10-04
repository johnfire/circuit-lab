import { useState } from 'react';
import { useSharedCircuit } from './use-shared-circuit';
import type { EditorState } from './use-schematic-editor';

export function AnalogProjectControls({ editor }: { editor: EditorState }) {
  const sharing = useSharedCircuit(editor);
  const [name, setName] = useState('My circuit'), [client, setClient] = useState('');
  const selectedClient = client || sharing.status.clients[0] || '';
  const binding = sharing.workspace ?? sharing.saved;
  const disabled = sharing.busy || editor.running || !sharing.status.enabled;
  return <section className="editor-card collaboration-panel" aria-label="Saved circuits and AI sharing">
    <h2>Saved circuits &amp; your AI</h2><p role="status">{sharing.message}</p>
    <div className="project-actions"><label>Project name<input maxLength={80} value={name} onChange={event => setName(event.target.value)} /></label>
      <button disabled={disabled} onClick={() => { void sharing.save(name); }}>{sharing.saved ? 'Save project' : 'Save new project'}</button>
      {sharing.saved && <button disabled={disabled} onClick={() => { void sharing.save(name, true); }}>Save as new project</button>}
      <label>Saved projects<select value={sharing.saved?.document ?? ''} disabled={disabled || Boolean(sharing.workspace)}
        onChange={event => { if (event.target.value) void sharing.open(event.target.value); }}><option value="">Choose a saved project…</option>
        {sharing.projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
      <label>Recover shared workspace<select value={sharing.workspace?.document ?? ''} disabled={disabled || Boolean(sharing.workspace)}
        onChange={event => { if (event.target.value) void sharing.open(event.target.value); }}><option value="">Choose a previous workspace…</option>
        {sharing.workspaces.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>
      {binding && <button disabled={disabled || !binding.parent} onClick={() => { void sharing.undo(); }}>Undo server change</button>}
      {binding && <button disabled={disabled || Boolean(sharing.incoming)} onClick={() => { void sharing.simulate(); }}>Run shared revision</button>}
    </div>
    <div className="project-actions"><label>Registered AI client<select value={selectedClient} onChange={event => setClient(event.target.value)}>
      {!sharing.status.clients.length && <option value="">No OAuth clients configured yet</option>}
      {sharing.status.clients.map(identifier => <option key={identifier}>{identifier}</option>)}</select></label>
      <button disabled={disabled || !selectedClient || Boolean(sharing.incoming)} onClick={() => { void sharing.share(selectedClient, name + ' · live tab', 'workspace'); }}>Share this grid with my AI</button>
      <button disabled={disabled || !selectedClient || !sharing.saved} onClick={() => { void sharing.share(selectedClient, name, 'project'); }}>Share saved project</button>
      {binding && <button disabled={disabled} onClick={() => { void sharing.stop(); }}>Stop sharing</button>}
    </div>
    {sharing.workspace && <p>Live workspace: <code>{sharing.workspace.document}</code> · {sharing.connected ? 'Sharing active' : 'No active AI grants'}
      <br />Revision: <code>{sharing.workspace.revision}</code>. Each tab has its own workspace.</p>}
    {sharing.incoming && <div role="alert"><p>Unsent local changes were kept. Export your draft or save it as a new project before replacing it.</p>
      <button disabled={sharing.busy || editor.running} onClick={sharing.acceptIncoming}>Use server revision</button></div>}
    {sharing.status.enabled && <p>MCP endpoint: <code>{sharing.status.endpoint}</code>. OAuth sign-in is required; never paste credentials into a chat.</p>}
    <p className="muted">Sharing lets your chosen external AI provider receive this circuit and simulation results. Grants expire after 30 minutes.
      Stop sharing blocks further access but cannot retract copies already received.</p>
    <details><summary>Change history ({sharing.history.length})</summary><ol>{sharing.history.map(revision =>
      <li key={revision.revision}>{revision.actor} — {revision.reason} <time>{revision.created_at}</time></li>)}</ol></details>
  </section>;
}
