export function frameAt(times: number[], seconds: number): number {
  let low = 0, high = times.length - 1;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (times[middle] <= seconds) low = middle; else high = middle - 1;
  }
  return low;
}

export function advanceTime(current: number, elapsed: number, rate: number, bounds: [number, number], loop: boolean): number {
  const next = current + Math.max(0, elapsed) * rate;
  const [start, end] = bounds;
  if (next <= end) return Math.max(start, next);
  return loop && end > start ? start + ((next - start) % (end - start)) : end;
}
