import { downloadJson } from './schematic-files';
import { starterCircuit } from './schematic-model';
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
    <button onClick={() => downloadJson('circuit-lab-schematic.json', editor.schematic)}>Export circuit</button>
    <label className="file-button">Import circuit<input type="file" accept=".json,application/json" disabled={editor.running}
      onChange={event => { void importFile(event.target.files?.[0]); event.target.value = ''; }} /></label>
    <button onClick={() => downloadJson('circuit-lab-session-history.json', editor.history.current)}>Export edit history</button>
  </div>;
}
