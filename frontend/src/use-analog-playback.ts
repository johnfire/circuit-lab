import { useEffect, useState } from 'react';
import { advanceTime, frameAt } from './schematic-playback';
import type { AnalogReport } from './schematic-types';

export function useAnalogPlayback(report: AnalogReport) {
  const last = report.times.at(-1) ?? 0;
  const [cursor, setCursor] = useState(() => report.times.find((_, index) =>
    report.traces.some(trace => Math.abs(trace.values[index]) > 1e-9)) ?? 0);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  const [rate, setRate] = useState(.01);
  const [bounds, setBounds] = useState<[number, number]>([0, last]);
  const index = frameAt(report.times, cursor);
  const atEnd = !loop && cursor >= bounds[1];
  useEffect(() => { if (atEnd && playing) setPlaying(false); }, [atEnd, playing]);
  useEffect(() => {
    if (!playing || atEnd) return;
    let previous: number | undefined;
    let animation = 0;
    const tick = (clock: number) => {
      const elapsed = previous === undefined ? 0 : (clock - previous) / 1000;
      setCursor(time => advanceTime(time, elapsed, rate, bounds, loop));
      previous = clock;
      animation = requestAnimationFrame(tick);
    };
    animation = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animation);
  }, [playing, rate, bounds, loop, atEnd]);
  const toggle = () => { if (atEnd) setCursor(bounds[0]); setPlaying(atEnd || !playing); };
  const seek = (seconds: number) => { setPlaying(false); setCursor(Math.max(bounds[0], Math.min(bounds[1], seconds))); };
  const step = (direction: number) => seek(report.times[Math.max(0, Math.min(report.times.length - 1, index + direction))]);
  const window = (next: [number, number]) => {
    if (next[0] >= 0 && next[1] <= last && next[1] > next[0]) { setBounds(next); setPlaying(false); setCursor(next[0]); }
  };
  return { index, cursor, playing: playing && !atEnd, loop, rate, bounds, toggle, seek, step, window, setLoop, setRate };
}
