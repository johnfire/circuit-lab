import { message } from './display-message.ts';
import { translate } from './localization.ts';
import { downloadJson } from './schematic-files';
import { starterCircuit } from './schematic-model';
import { sineExample } from './analog-examples';
import type { EditorState } from './use-schematic-editor';

export function AnalogFileControls({ editor }: { editor: EditorState }) {
  const importFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 8192) { editor.setError(message("analog-file-controls.circuit_files_must_be_at")); return; }
    try { editor.importText(await file.text()); }
    catch { editor.setError(message("analog-file-controls.the_circuit_file_could_not")); }
  };
  const replace = (blank: boolean) => {
    if (!window.confirm(translate("analog-file-controls.replace_the_current_browser_draft"))) return;
    const schematic = starterCircuit();
    editor.commit(blank ? { ...schematic, parts: [], wires: [] } : schematic, blank ? 'circuit.new' : 'circuit.example');
    editor.setSelected(blank ? null : 'R1'); editor.setWireStart(null); editor.setArmed(null);
  };
  return <div className="editor-file-controls"><button disabled={editor.running} onClick={() => replace(true)}>{translate("analog-file-controls.new_blank")}</button>
    <button disabled={editor.running} onClick={() => replace(false)}>{translate("analog-file-controls.rc_example")}</button>
    <label>{translate("analog-file-controls.ac_example")}<select aria-label={translate("analog-file-controls.ac_example")} disabled={editor.running} defaultValue="" onChange={event => {
      if (event.target.value && window.confirm(translate("analog-file-controls.replace_the_current_draft_with"))) {
        editor.commit(sineExample(event.target.value as 'R' | 'C' | 'L'), 'circuit.ac-example'); editor.setSelected('R1');
      }
      event.target.value = '';
    }}><option value="">{translate("analog-file-controls.choose")}</option><option value="R">{translate("analog-file-controls.resistive_ac")}</option><option value="C">{translate("analog-file-controls.rc_lowpass")}</option><option value="L">{translate("analog-file-controls.rl_phase")}</option></select></label>
    <button onClick={() => downloadJson('circuit-lab-schematic.json', { version: 2, circuit: editor.schematic })}>{translate("analog-file-controls.export_circuit")}</button>
    <label className="file-button">{translate("analog-file-controls.import_circuit")}<input type="file" accept=".json,application/json" disabled={editor.running}
      onChange={event => { void importFile(event.target.files?.[0]); event.target.value = ''; }} /></label>
    <button onClick={() => downloadJson('circuit-lab-session-history.json', editor.history.current)}>{translate("analog-file-controls.export_edit_history")}</button>
  </div>;
}
