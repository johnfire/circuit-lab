import { useState } from 'react';
import { exportKicad } from './schematic-api';
import { downloadText } from './schematic-files';
import type { EditorState } from './use-schematic-editor';

/** Download a KiCad netlist and JLCPCB BOM, then list what still needs checking before ordering. */
export function PcbExport({ editor }: { editor: EditorState }) {
  const [notes, setNotes] = useState<string[] | null>(null), [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const files = await exportKicad(editor.schematic);
      downloadText('circuit-lab.net', files.netlist, 'text/plain');
      downloadText('circuit-lab-bom.csv', files.bom_csv, 'text/csv');
      setNotes(files.warnings);
    } catch (error) { editor.setError(error instanceof Error ? error.message : 'PCB export failed.'); setNotes(null); }
    finally { setBusy(false); }
  };
  return <section className="editor-card" aria-label="PCB export">
    <h2>Order a PCB</h2>
    <p className="muted">Exports a KiCad netlist (circuit-lab.net) and a JLCPCB-style parts list (circuit-lab-bom.csv). In KiCad's PCB
      editor, import the netlist, place and route, then plot Gerbers and drill files to upload to JLCPCB or PCBWay.</p>
    <button disabled={busy || editor.running} onClick={() => { void run(); }}>{busy ? 'Exporting…' : 'Export for PCB (KiCad)'}</button>
    {notes && <><h3>Before you order</h3><ul className="model-warnings">{notes.map(note => <li key={note}>{note}</li>)}</ul></>}
  </section>;
}
