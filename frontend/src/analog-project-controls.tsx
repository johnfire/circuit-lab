import { formatTimestamp } from './display-numbers.ts';
import { displayMessage } from './display-message.ts';
import { translate } from './localization.ts';
import { useState } from 'react';
import { useSharedCircuit } from './use-shared-circuit';
import type { EditorState } from './use-schematic-editor';

export function AnalogProjectControls({ editor }: { editor: EditorState }) {
  const sharing = useSharedCircuit(editor);
  const [name, setName] = useState(translate("analog-project-controls.my_circuit")), [client, setClient] = useState('');
  const selectedClient = client || sharing.status.clients[0] || '';
  const binding = sharing.workspace ?? sharing.saved;
  const disabled = sharing.busy || editor.running || !sharing.status.enabled;
  return <section className="editor-card collaboration-panel" aria-label={translate("analog-project-controls.saved_circuits_and_ai_sharing")}>
    <h2>{translate("analog-project-controls.saved_circuits_your_ai")}</h2><p role="status">{displayMessage(sharing.message)}</p>
    <div className="project-actions"><label>{translate("analog-project-controls.project_name")}<input maxLength={80} value={name} onChange={event => setName(event.target.value)} /></label>
      <button disabled={disabled} onClick={() => { void sharing.save(name); }}>{sharing.saved ? translate("analog-project-controls.save_project") : translate("analog-project-controls.save_new_project")}</button>
      {sharing.saved && <button disabled={disabled} onClick={() => { void sharing.save(name, true); }}>{translate("analog-project-controls.save_as_new_project")}</button>}
      <label>{translate("analog-project-controls.saved_projects")}<select value={sharing.saved?.document ?? ''} disabled={disabled || Boolean(sharing.workspace)}
        onChange={event => { if (event.target.value) void sharing.open(event.target.value); }}><option value="">{translate("analog-project-controls.choose_a_saved_project")}</option>
        {sharing.projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
      <label>{translate("analog-project-controls.recover_shared_workspace")}<select value={sharing.workspace?.document ?? ''} disabled={disabled || Boolean(sharing.workspace)}
        onChange={event => { if (event.target.value) void sharing.open(event.target.value); }}><option value="">{translate("analog-project-controls.choose_a_previous_workspace")}</option>
        {sharing.workspaces.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>
      {binding && <button disabled={disabled || !binding.parent} onClick={() => { void sharing.undo(); }}>{translate("analog-project-controls.undo_server_change")}</button>}
      {binding && <button disabled={disabled || Boolean(sharing.incoming)} onClick={() => { void sharing.simulate(); }}>{translate("analog-project-controls.run_shared_revision")}</button>}
    </div>
    <div className="project-actions"><label>{translate("analog-project-controls.registered_ai_client")}<select value={selectedClient} onChange={event => setClient(event.target.value)}>
      {!sharing.status.clients.length && <option value="">{translate("analog-project-controls.no_oauth_clients_configured_yet")}</option>}
      {sharing.status.clients.map(identifier => <option key={identifier}>{identifier}</option>)}</select></label>
      <button disabled={disabled || !selectedClient || Boolean(sharing.incoming)} onClick={() => { void sharing.share(selectedClient, name + translate("analog-project-controls.live_tab"), 'workspace'); }}>{translate("analog-project-controls.share_this_grid_with_my")}</button>
      <button disabled={disabled || !selectedClient || !sharing.saved} onClick={() => { void sharing.share(selectedClient, name, 'project'); }}>{translate("analog-project-controls.share_saved_project")}</button>
      {binding && <button disabled={disabled} onClick={() => { void sharing.stop(); }}>{translate("analog-project-controls.stop_sharing")}</button>}
    </div>
    {sharing.workspace && <p>{translate("analog-project-controls.live_workspace")}<code>{sharing.workspace.document}</code> · {sharing.connected ? translate("analog-project-controls.sharing_active") : translate("analog-project-controls.no_active_ai_grants")}
      <br />{translate("analog-project-controls.revision")}<code>{sharing.workspace.revision}</code>{translate("analog-project-controls.each_tab_has_its_own")}</p>}
    {sharing.incoming && <div role="alert"><p>{translate("analog-project-controls.unsent_local_changes_were_kept")}</p>
      <button disabled={sharing.busy || editor.running} onClick={sharing.acceptIncoming}>{translate("analog-project-controls.use_server_revision")}</button></div>}
    {sharing.status.enabled && <p>{translate("analog-project-controls.mcp_endpoint")}<code>{sharing.status.endpoint}</code>{translate("analog-project-controls.oauth_signin_is_required_never")}</p>}
    <p className="muted">{translate("analog-project-controls.sharing_lets_your_chosen_external")}</p>
    <details><summary>{translate("analog-project-controls.change_history")}{sharing.history.length})</summary><ol>{sharing.history.map(revision =>
      <li key={revision.revision}>{revision.actor} — {revision.reason} <time>{formatTimestamp(revision.created_at)}</time></li>)}</ol></details>
  </section>;
}
