import { downloadJson } from './schematic-files';
import { starterCircuit } from './schematic-model';
import { sineExample } from './analog-examples';
import type { EditorState } from './use-schematic-editor';

export function AnalogFileControls({ editor }: { editor: EditorState }) {
  const importFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 8192) { editor.setError('Circuit files must be at most 8 KB.'); return; }
    try { editor.importText(await file.text()); }
    catch { editor.setError('The circuit file could not be read.'); }
  };
  const replace = (blank: boolean) => {
    if (!window.confirm('Replace the current browser draft? Export first if you want to keep it.')) return;
    const schematic = starterCircuit();
    editor.commit(blank ? { ...schematic, parts: [], wires: [] } : schematic, blank ? 'circuit.new' : 'circuit.example');
    editor.setSelected(blank ? null : 'R1'); editor.setWireStart(null); editor.setArmed(null);
  };
  return <div className="editor-file-controls"><button disabled={editor.running} onClick={() => replace(true)}>New blank</button>
    <button disabled={editor.running} onClick={() => replace(false)}>RC example</button>
    <label>AC example<select aria-label="AC example" disabled={editor.running} defaultValue="" onChange={event => {
      if (event.target.value && window.confirm('Replace the current draft with an AC example? Export first to keep it.')) {
        editor.commit(sineExample(event.target.value as 'R' | 'C' | 'L'), 'circuit.ac-example'); editor.setSelected('R1');
      }
      event.target.value = '';
    }}><option value="">Choose…</option><option value="R">Resistive AC</option><option value="C">RC low-pass</option><option value="L">RL phase</option></select></label>
    <button onClick={() => downloadJson('circuit-lab-schematic.json', { version: 2, circuit: editor.schematic })}>Export circuit</button>
    <label className="file-button">Import circuit<input type="file" accept=".json,application/json" disabled={editor.running}
      onChange={event => { void importFile(event.target.files?.[0]); event.target.value = ''; }} /></label>
    <button onClick={() => downloadJson('circuit-lab-session-history.json', editor.history.current)}>Export edit history</button>
  </div>;
}
