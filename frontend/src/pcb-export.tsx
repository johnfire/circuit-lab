import { message, failureMessage } from './display-message.ts';
import { translate } from './localization.ts';
import { useState } from 'react';
import { parseMessage } from './report-localization.ts';
import { displayMessage, type DisplayMessage } from './display-message.ts';
import { exportBringUp, exportKicad } from './schematic-api';
import { downloadText } from './schematic-files';
import type { EditorState } from './use-schematic-editor';

/** Download a KiCad netlist, JLCPCB BOM, design rules and step-by-step guide, then list what still needs checking. */
export function PcbExport({ editor }: { editor: EditorState }) {
  const [notes, setNotes] = useState<DisplayMessage[] | null>(null), [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const files = await exportKicad(editor.schematic);
      downloadText('circuit-lab.net', files.netlist, 'text/plain');
      downloadText('circuit-lab-bom.csv', files.bom_csv, 'text/csv');
      downloadText('circuit-lab-jlcpcb-rules.txt', files.design_rules, 'text/plain');
      downloadText('circuit-lab-pcb-steps.md', files.fab_guide, 'text/markdown');
      setNotes(files.warnings.map((warning, index) => parseMessage(files.warning_messages?.[index]) ?? warning));
    } catch (error) { editor.setError(error instanceof Error ? failureMessage(error) : message("pcb-export.pcb_export_failed")); setNotes(null); }
    finally { setBusy(false); }
  };
  const bringUp = async () => {
    setBusy(true);
    try { downloadText('circuit-lab-bring-up.md', await exportBringUp(editor.schematic), 'text/markdown'); }
    catch (error) { editor.setError(error instanceof Error ? failureMessage(error) : message("pcb-export.bringup_checklist_failed")); }
    finally { setBusy(false); }
  };
  return <section className="editor-card" aria-label={translate("pcb-export.pcb_export")}>
    <h2>{translate("pcb-export.order_a_pcb")}</h2>
    <p className="muted">{translate("pcb-export.downloads_four_files_the_kicad")}</p>
    <div className="button-row"><button disabled={busy || editor.running} onClick={() => { void run(); }}>{busy ? translate('common.exporting') : translate("pcb-export.export_for_pcb_kicad")}</button>
      <button disabled={busy || editor.running} onClick={() => { void bringUp(); }}>{translate("pcb-export.bringup_checklist")}</button></div>
    <p className="muted">{translate("pcb-export.the_bringup_checklist_simulates_the")}</p>
    {notes && <><h3>{translate("pcb-export.before_you_order")}</h3><ul className="model-warnings">{notes.map((note, index) => <li key={index}>{displayMessage(note)}</li>)}</ul></>}
  </section>;
}
