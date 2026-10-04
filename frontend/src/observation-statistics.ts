export interface WindowStatistics { mean: number; rms: number; acRms: number; peakToPeak: number; samples: number }
interface SineFit { offset: number; amplitude: number; phase: number; residual: number }

/** Time-weighted statistics include every solver output sample inside the selected window. */
export function windowStatistics(times: number[], coefficients: number[], bounds: [number, number]): WindowStatistics | null {
  const indices = times.map((time, index) => ({ time, index })).filter(({ time }) => time >= bounds[0] && time <= bounds[1]);
  if (indices.length < 2) return null;
  let area = 0, squaredArea = 0;
  for (let index = 1; index < indices.length; index++) {
    const previous = indices[index - 1], current = indices[index];
    const duration = current.time - previous.time;
    area += duration * (coefficients[current.index] + coefficients[previous.index]) / 2;
    squaredArea += duration * (coefficients[current.index] ** 2 + coefficients[previous.index] ** 2) / 2;
  }
  const duration = indices.at(-1)!.time - indices[0].time;
  const mean = area / duration, rms = Math.sqrt(Math.max(0, squaredArea / duration));
  const samples = indices.map(({ index }) => coefficients[index]);
  return { mean, rms, acRms: Math.sqrt(Math.max(0, rms ** 2 - mean ** 2)),
    peakToPeak: Math.max(...samples) - Math.min(...samples), samples: samples.length };
}

function solveCoefficients(matrix: number[][]): number[] | null {
  const augmented = matrix.map(row => [...row]);
  for (let column = 0; column < 3; column++) {
    const pivot = augmented[column][column];
    if (Math.abs(pivot) < 1e-12) return null;
    augmented[column] = augmented[column].map(coefficient => coefficient / pivot);
    for (let row = 0; row < 3; row++) {
      if (row === column) continue;
      const factor = augmented[row][column];
      augmented[row] = augmented[row].map((coefficient, index) => coefficient - factor * augmented[column][index]);
    }
  }
  return augmented.map(row => row[3]);
}

function fitSine(times: number[], coefficients: number[], frequency: number, bounds: [number, number]): SineFit | null {
  const samples = times.map((time, index) => ({ time, coefficient: coefficients[index] }))
    .filter(({ time }) => time >= bounds[0] && time <= bounds[1]);
  if (samples.length < 20) return null;
  const matrix = Array.from({ length: 3 }, () => [0, 0, 0, 0]);
  for (const sample of samples) {
    const basis = [1, Math.sin(2 * Math.PI * frequency * sample.time), Math.cos(2 * Math.PI * frequency * sample.time)];
    for (let row = 0; row < 3; row++) {
      for (let column = 0; column < 3; column++) matrix[row][column] += basis[row] * basis[column];
      matrix[row][3] += basis[row] * sample.coefficient;
    }
  }
  const fitted = solveCoefficients(matrix);
  if (!fitted) return null;
  const [offset, sine, cosine] = fitted, amplitude = Math.hypot(sine, cosine);
  if (amplitude < 1e-12) return null;
  const squaredResidual = samples.reduce((sum, { time, coefficient }) => sum + (coefficient - offset -
    sine * Math.sin(2 * Math.PI * frequency * time) - cosine * Math.cos(2 * Math.PI * frequency * time)) ** 2, 0);
  return { offset, amplitude, phase: Math.atan2(cosine, sine) * 180 / Math.PI,
    residual: Math.sqrt(squaredResidual / samples.length) / amplitude };
}

/** Conservative qualification: >=3 cycles, adequate sampling, low distortion and stable consecutive cycles. */
export function settledPhase(times: number[], coefficients: number[], frequency: number, bounds: [number, number]): number | null {
  if ((bounds[1] - bounds[0]) * frequency < 3 || (times[1] - times[0]) * frequency > 1 / 40) return null;
  const fit = fitSine(times, coefficients, frequency, bounds);
  const latest = fitSine(times, coefficients, frequency, [bounds[1] - 1 / frequency, bounds[1]]);
  const previous = fitSine(times, coefficients, frequency, [bounds[1] - 2 / frequency, bounds[1] - 1 / frequency]);
  if (!fit || !latest || !previous || fit.residual > .03 || latest.residual > .03 || previous.residual > .03) return null;
  if (Math.abs(latest.amplitude / previous.amplitude - 1) > .02 ||
    Math.abs(((latest.phase - previous.phase + 540) % 360) - 180) > 2 ||
    Math.abs(latest.offset - previous.offset) > .02 * latest.amplitude) return null;
  return fit.phase;
}
