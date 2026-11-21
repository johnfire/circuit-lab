import { message } from './display-message.ts';
import { useEffect, useRef } from 'react';
import { frameAt } from './schematic-playback';
import { projectRequest } from './project-api';
import type { EditorState } from './use-schematic-editor';
import type { ObservationReport, Probe } from './schematic-types';

/** Acknowledgement follows rendered cursor/probe changes, never merely receiving a request. */
export function useAIObservationView(editor: EditorState, report: ObservationReport, frame: number,
  seek: (index: number) => void, replace: (probes: Probe[]) => void) {
  const applied = useRef('');
  const acknowledged = useRef('');
  const rendered = useRef<{ id: string | undefined; correlation: string; frame: number } | null>(null);
  useEffect(() => {
    rendered.current = { id: editor.remoteView?.id, correlation: report.correlation_id, frame };
    return () => { rendered.current = null; };
  }, [editor.remoteView?.id, report.correlation_id, frame]);
  useEffect(() => {
    const view = editor.remoteView;
    if (!view || editor.running) return;
    const isAC = report.analysis === 'ac';
    if ((view.time !== null && isAC) || (view.frequency !== null && !isAC)) return;
    const axis = isAC ? report.frequencies : report.times;
    const cursor = isAC ? view.frequency : view.time;
    if (cursor !== null && (cursor < axis[0] || cursor > axis.at(-1)!)) return;
    const desiredFrame = cursor === null ? frame : frameAt(axis, cursor);
    if (view.id !== applied.current) {
      applied.current = view.id;
      if (cursor !== null) seek(desiredFrame);
      if (view.pins.length) replace(view.pins.map(pin => ({ kind: 'node', pin })));
      if (view.pins[0]) editor.setSelected(view.pins[0].part);
    }
    if (frame !== desiredFrame || acknowledged.current === view.id) return;
    requestAnimationFrame(() => { requestAnimationFrame(() => {
      if (rendered.current?.id !== view.id || rendered.current.correlation !== report.correlation_id
        || rendered.current.frame !== desiredFrame || acknowledged.current === view.id) return;
      acknowledged.current = view.id;
      void projectRequest('/' + view.document + '/view/' + view.id + '/acknowledge', {}).catch(() => {
        editor.setError(message("ai-observation-view.ai_observation_changed_but_acknowledgement"));
      });
    }); });
  }, [editor, report, frame, seek, replace]);
}
