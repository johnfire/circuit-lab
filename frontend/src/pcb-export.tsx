import { useState } from 'react';
import { exportKicad } from './schematic-api';
import { downloadText } from './schematic-files';
import type { EditorState } from './use-schematic-editor';

/** Download a KiCad netlist, JLCPCB BOM, design rules and step-by-step guide, then list what still needs checking. */
export function PcbExport({ editor }: { editor: EditorState }) {
  const [notes, setNotes] = useState<string[] | null>(null), [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const files = await exportKicad(editor.schematic);
      downloadText('circuit-lab.net', files.netlist, 'text/plain');
      downloadText('circuit-lab-bom.csv', files.bom_csv, 'text/csv');
      downloadText('circuit-lab-jlcpcb-rules.txt', files.design_rules, 'text/plain');
      downloadText('circuit-lab-pcb-steps.md', files.fab_guide, 'text/markdown');
      setNotes(files.warnings);
    } catch (error) { editor.setError(error instanceof Error ? error.message : 'PCB export failed.'); setNotes(null); }
    finally { setBusy(false); }
  };
  return <section className="editor-card" aria-label="PCB export">
    <h2>Order a PCB</h2>
    <p className="muted">Downloads four files: the KiCad netlist (circuit-lab.net), a JLCPCB-style parts list (circuit-lab-bom.csv),
      JLCPCB design rules to paste into KiCad (circuit-lab-jlcpcb-rules.txt) and the steps from KiCad to an order
      (circuit-lab-pcb-steps.md). Your browser may ask once to allow several downloads.</p>
    <button disabled={busy || editor.running} onClick={() => { void run(); }}>{busy ? 'Exporting…' : 'Export for PCB (KiCad)'}</button>
    {notes && <><h3>Before you order</h3><ul className="model-warnings">{notes.map(note => <li key={note}>{note}</li>)}</ul></>}
  </section>;
}
