import { useMemo, useState } from 'react';
import { voltageScale } from './observation-signals';
import { AnalogMeasurements } from './analog-measurements';
import { AnalogTimeline } from './analog-timeline';
import { ACMeasurements } from './observation-ac-measurements';
import { ObservationScope } from './observation-scope';
import { ObservationToolbar, FrequencyCursor, TimePlaybackControls } from './observation-toolbar';
import { ObservationCycleControls } from './observation-cycle-controls';
import { ObservationProbesPanel } from './observation-probes-panel';
import { ObservationDisplayControls } from './observation-display-controls';
import { SchematicCanvas } from './schematic-canvas';
import { useObservationProbes } from './use-observation-probes';
import { useAnalogPlayback } from './use-analog-playback';
import type { DisplayControls } from './observation-display-controls';
import type { ObservationControls } from './observation-toolbar';
import type { EditorState } from './use-schematic-editor';
import type { AnalogReport, ObservationReport } from './schematic-types';

function useObservationDisplay(): DisplayControls {
  const [markers, setMarkers] = useState(false), [shading, setShading] = useState(false), [beside, setBeside] = useState(false);
  return { markers, shading, beside, setMarkers, setShading, setBeside };
}

interface SessionProps { editor: EditorState; report: ObservationReport; controls: ObservationControls }
interface Clock { frame: number; bounds: [number, number]; onSeek: (index: number) => void; playing: boolean }

function ObservationGridAndScope({ editor, report, controls, clock }: SessionProps & { clock: Clock }) {
  const probes = useObservationProbes(editor.schematic), display = useObservationDisplay();
  const voltageLimit = useMemo(() => voltageScale(report), [report]);
  const observation = { observing: controls.observing, markers: display.markers, shading: display.shading, playing: clock.playing,
    onPin: probes.pin, onCurrent: (part: string) => probes.add({ kind: 'current', part }) };
  return <><div className={'observation-split ' + (display.beside ? 'scope-beside' : '')}>
    <SchematicCanvas editor={editor} report={report} frame={clock.frame} observation={observation} />
    <ObservationScope report={report} schematic={editor.schematic} probes={probes.probes} frame={clock.frame} bounds={clock.bounds} onSeek={clock.onSeek} /></div>
    <section className="editor-card"><h2>Observation tools</h2><ObservationProbesPanel schematic={editor.schematic} controller={probes} />
      <ObservationDisplayControls controls={display} frequency={report.analysis === 'ac'} voltageLimit={voltageLimit} /></section>
  </>;
}

function TransientSession({ editor, report, controls }: SessionProps & { report: AnalogReport }) {
  const playback = useAnalogPlayback(report);
  const clock = { frame: playback.index, bounds: playback.bounds, onSeek: (index: number) => playback.seek(report.times[index]), playing: playback.playing };
  return <><ObservationToolbar editor={editor} controls={controls}><TimePlaybackControls playback={playback} report={report} /></ObservationToolbar>
    <ObservationGridAndScope editor={editor} report={report} controls={controls} clock={clock} />
    <AnalogTimeline playback={playback} report={report} /><section className="editor-card"><h2>AC cycle window</h2>
      <ObservationCycleControls schematic={editor.schematic} playback={playback} /></section>
    <AnalogMeasurements schematic={editor.schematic} report={report} frame={playback.index} /></>;
}

export function AnalogObservationSession(props: SessionProps) {
  const [frame, setFrame] = useState(0);
  const report = props.report;
  if (report.analysis !== 'ac') return <TransientSession {...props} report={report} />;
  const clock: Clock = { frame, bounds: [report.frequencies[0], report.frequencies.at(-1)!], onSeek: setFrame, playing: false };
  return <><ObservationToolbar editor={props.editor} controls={props.controls}><FrequencyCursor report={report} frame={frame} onSeek={setFrame} /></ObservationToolbar>
    <ObservationGridAndScope {...props} clock={clock} /><ACMeasurements schematic={props.editor.schematic} report={report} frame={frame} /></>;
}
