import { useEffect, useRef } from 'react';
import { frameAt } from './schematic-playback';
import { projectRequest } from './project-api';
import type { EditorState } from './use-schematic-editor';
import type { ObservationReport, Probe } from './schematic-types';

/** Acknowledgement follows rendered cursor/probe changes, never merely receiving a request. */
export function useAIObservationView(editor: EditorState, report: ObservationReport, frame: number,
  seek: (index: number) => void, replace: (probes: Probe[]) => void) {
  const applied = useRef('');
  const rendered = useRef<{ id: string | undefined; correlation: string; frame: number } | null>(null);
  useEffect(() => {
    rendered.current = { id: editor.remoteView?.id, correlation: report.correlation_id, frame };
    return () => { rendered.current = null; };
  }, [editor.remoteView?.id, report.correlation_id, frame]);
  useEffect(() => {
    const view = editor.remoteView;
    if (!view || view.id === applied.current || editor.running) return;
    const isAC = report.analysis === 'ac';
    if ((view.time !== null && isAC) || (view.frequency !== null && !isAC)) return;
    const axis = isAC ? report.frequencies : report.times;
    const cursor = isAC ? view.frequency : view.time;
    if (cursor !== null && (cursor < axis[0] || cursor > axis.at(-1)!)) return;
    applied.current = view.id;
    const desiredFrame = cursor === null ? frame : frameAt(axis, cursor);
    if (cursor !== null) seek(desiredFrame);
    if (view.pins.length) replace(view.pins.map(pin => ({ kind: 'node', pin })));
    if (view.pins[0]) editor.setSelected(view.pins[0].part);
    requestAnimationFrame(() => { requestAnimationFrame(() => {
      if (rendered.current?.id !== view.id || rendered.current.correlation !== report.correlation_id || rendered.current.frame !== desiredFrame) return;
      void projectRequest('/' + view.document + '/view/' + view.id + '/acknowledge', {}).catch(() => {
        editor.setError('AI observation changed, but acknowledgement expired. The AI must request the current revision again.');
      });
    }); });
  }, [editor, report, frame, seek, replace]);
}
