import { useState } from 'react';
import { translate } from './localization';
import { downloadText } from './schematic-files';
import type { Schematic } from './schematic-types';

interface Finding { description: string; severity: string }
interface Review { board: string; origin: 'generated' | 'imported'; layers: Record<string, string>;
  drc: { violations: Finding[]; unconnected_items: Finding[] }; warnings: string[];
  track_items: number; components: { reference: string; value: string; x_mm: number; y_mm: number }[] }

export function PcbReview({ circuit }: { circuit: Schematic }) {
  const [review, setReview] = useState<Review | null>(null);
  const [fingerprint, setFingerprint] = useState('');
  const [width, setWidth] = useState(90), [height, setHeight] = useState(45);
  const [layer, setLayer] = useState('front'), [zoom, setZoom] = useState(100);
  const [busy, setBusy] = useState(false), [failed, setFailed] = useState(false);
  const submit = async (path: string, body: BodyInit, type: string) => {
    setBusy(true); setFailed(false);
    try {
      const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': type }, body, signal: AbortSignal.timeout(120000) });
      if (!response.ok) throw new Error('PCB processing failed');
      setReview(await response.json() as Review); setFingerprint(JSON.stringify(circuit));
    } catch { setFailed(true); } finally { setBusy(false); }
  };
  const upload = (file: File | undefined) => {
    if (!file) return;
    if (file.size > 1_048_576) { setFailed(true); return; }
    void submit('/api/pcb/review', file, 'application/octet-stream');
  };
  return <section className="editor-card pcb-review" aria-label={translate('pcb.review')}>
    <h2>{translate('pcb.review')}</h2><p>{translate('pcb.intro')}</p>
    <div className="compact-fields"><label>{translate('pcb.width')}<input type="number" min="20" max="300" step="1" value={width} onChange={event => setWidth(Number(event.target.value))} /></label>
      <label>{translate('pcb.height')}<input type="number" min="20" max="300" step="1" value={height} onChange={event => setHeight(Number(event.target.value))} /></label></div>
    <div className="button-row"><button disabled={busy} onClick={() => { void submit('/api/pcb/generate', JSON.stringify({ circuit, width_mm: width, height_mm: height }), 'application/json'); }}>{translate('pcb.generate')}</button>
      <label className="file-button">{translate('pcb.import')}<input type="file" accept=".kicad_pcb" disabled={busy} onChange={event => { upload(event.target.files?.[0]); event.target.value = ''; }} /></label></div>
    {busy && <p role="status">{translate('pcb.processing')}</p>}{failed && <p role="alert">{translate('pcb.failed')}</p>}
    {review && <><p role="status">{translate(review.origin === 'generated' ? 'pcb.generated' : 'pcb.imported')}</p>
      {review.origin === 'generated' && fingerprint !== JSON.stringify(circuit) && <p role="alert">{translate('pcb.stale')}</p>}
      <p>{translate('pcb.rules_notice')}</p>{review.warnings.length > 0 && <details><summary>{translate('pcb.warnings')}</summary><ul>{review.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}<label>{translate('pcb.layer')}<select value={layer} onChange={event => setLayer(event.target.value)}>
        <option value="front">{translate('pcb.front')}</option><option value="back">{translate('pcb.back')}</option><option value="outline">{translate('pcb.outline')}</option></select></label>
      <label>{translate('pcb.zoom')}<input type="range" min="50" max="300" step="25" value={zoom} onChange={event => setZoom(Number(event.target.value))} /> {zoom}%</label>
      <div className="pcb-image-scroll" tabIndex={0} role="region" aria-label={translate('pcb.board_view')}><img style={{ width: `${zoom}%` }} src={'data:image/png;base64,' + review.layers[layer]} alt={translate('pcb.board_view')} /></div>
      <p>{translate('pcb.tracks', { count: review.track_items })} · {translate('pcb.unconnected', { count: review.drc.unconnected_items.length })} · {translate('pcb.violations', { count: review.drc.violations.length })}</p>
      {[...review.drc.violations, ...review.drc.unconnected_items].length > 0 && <details><summary>{translate('pcb.findings')}</summary><ul>{[...review.drc.violations, ...review.drc.unconnected_items].map((finding, index) => <li key={index}>{finding.description}</li>)}</ul></details>}
      <details><summary>{translate('pcb.components')}</summary><ul>{review.components.map(part => <li key={part.reference}>{part.reference} · {part.value} · {part.x_mm.toFixed(2)}, {part.y_mm.toFixed(2)}{' mm'}</li>)}</ul></details>
      <button onClick={() => downloadText('circuit-lab-board.kicad_pcb', review.board, 'text/plain')}>{translate('pcb.download')}</button></>}
  </section>;
}
