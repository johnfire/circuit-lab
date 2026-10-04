import assert from 'node:assert/strict';
import test from 'node:test';
import { magnitude, probeSignal, relativePhase, extremaIndices, unwrapPhases, voltageScale, tintedVoltage } from '../src/observation-signals.ts';
import { sineExample } from '../src/analog-examples.ts';
import { nodeLabels, wireBoxes, overlaps, observationViewBox } from '../src/observation-layout.ts';
import { analysisFailureMessage } from '../src/schematic-api.ts';
import { windowStatistics, settledPhase } from '../src/observation-statistics.ts';
import { scopeSeries } from '../src/observation-scope-series.ts';
import { signalReading } from '../src/observation-readings.ts';
import { parseSchematic } from '../src/schematic-files.ts';
import { starterCircuit } from '../src/schematic-model.ts';
import type { ACReport, AnalogReport } from '../src/schematic-types.ts';

const ac: ACReport = { analysis: 'ac', status: 'completed', correlation_id: 'math',
  frequencies: [10, 100], excitation: { source: 'V1', amplitude: 2, phase: 30, start: 10, stop: 100, spacing: 'linear', points: 2 },
  dc_biases: { V1: 0 }, pin_nodes: { 'R1:0': 'n1', 'R1:1': '0' }, netlist: '', warnings: [],
  traces: [{ name: 'V:n1', unit: 'V', real: [1, 0], imaginary: [-1, 0] },
    { name: 'I:R1', unit: 'A', real: [.001, 0], imaginary: [.001, 0] }] };

test('node/differential/current complex probes preserve signs and never invent missing zero', () => {
  const signal = probeSignal(ac, { kind: 'differential', first: { part: 'R1', terminal: 0 }, second: { part: 'R1', terminal: 1 } });
  assert.deepEqual(signal?.real, [1, 0]); assert.deepEqual(signal?.imaginary, [-1, 0]);
  assert.equal(probeSignal(ac, { kind: 'node', pin: { part: 'missing', terminal: 0 } }), null);
  assert.equal(probeSignal(ac, { kind: 'current', part: 'missing' }), null);
  assert.equal(relativePhase({ real: 1, imaginary: -1 }, 30), -75);
  assert.equal(relativePhase({ real: 0, imaginary: 0 }, 0), null);
  assert.equal(magnitude({ real: 3, imaginary: 4 }), 5);
  assert.match(signalReading(ac, signal, 0), /1.414 V ∠ -75.0°/);
});

test('gain normalization and dB gaps do not mix current and voltage units', () => {
  const voltage = probeSignal(ac, { kind: 'node', pin: { part: 'R1', terminal: 0 } })!;
  const current = probeSignal(ac, { kind: 'current', part: 'R1' })!;
  const series = scopeSeries(ac, [voltage, current], 'db');
  assert.ok(Math.abs(series[0].coefficients[0]! + 3.01029995664) < 1e-9);
  assert.equal(series[0].coefficients[1], null);
  assert.ok(Math.abs(series[1].coefficients[0]! - Math.sqrt(2) * .001) < 1e-12);
  assert.deepEqual(unwrapPhases([170, -170, -160, null, -90]), [170, 190, 200, null, -90]);
});

test('full-sample weighted RMS distinguishes offset from AC and qualifies settled phase', () => {
  const times = Array.from({ length: 401 }, (_, index) => index / 1000);
  const coefficients = times.map(time => 2 + 5 * Math.sin(2 * Math.PI * 10 * time + Math.PI / 4));
  const statistics = windowStatistics(times, coefficients, [0, .4])!;
  assert.ok(Math.abs(statistics.mean - 2) < 1e-12);
  assert.ok(Math.abs(statistics.rms - Math.sqrt(4 + 12.5)) < 1e-12);
  assert.ok(Math.abs(statistics.acRms - 5 / Math.sqrt(2)) < 1e-12);
  assert.ok(Math.abs(settledPhase(times, coefficients, 10, [0, .4])! - 45) < 1e-10);
  assert.equal(settledPhase(times, coefficients, 10, [0, .1]), null);
  assert.equal(settledPhase(times.map(time => time * 10), coefficients, 10, [0, 4]), null);
  const startup = times.map((time, index) => coefficients[index] + 4 * Math.exp(-time / .1));
  assert.equal(settledPhase(times, startup, 10, [0, .4]), null);
  assert.equal(settledPhase(times, times.map(() => 0), 10, [0, .4]), null);
  assert.equal(windowStatistics(times, coefficients, [.01, .0101]), null);
});

test('extrema reduction retains narrow spikes and gaps without modifying original samples', () => {
  const coefficients: (number | null)[] = Array(2001).fill(0);
  coefficients[729] = 100; coefficients[731] = -30; coefficients[1302] = null;
  const indices = extremaIndices(coefficients, 100);
  assert.ok(indices.includes(729)); assert.ok(indices.includes(731)); assert.ok(indices.includes(1302));
  assert.equal(coefficients.length, 2001); assert.equal(coefficients[729], 100);
});

test('legacy and version 2 circuit files round-trip while bounded sine values reject injection', () => {
  const legacy = starterCircuit();
  assert.deepEqual(parseSchematic(JSON.stringify(legacy)), legacy);
  const sine = { ...legacy, parts: legacy.parts.map(part => part.id === 'V1' ? { ...part, kind: 'SIN', pulse: null,
    sine: { offset: 0, frequency: 10, phase: 0 } } : part) };
  assert.deepEqual(parseSchematic(JSON.stringify({ version: 2, circuit: sine })), sine);
  assert.throws(() => parseSchematic(JSON.stringify({ version: 3, circuit: sine })), /version/);
  assert.throws(() => parseSchematic(JSON.stringify({ ...sine, parts: [{ ...sine.parts[0], sine: { offset: 0, frequency: '10 shell', phase: 0 } }] })), /outside/);
});

test('transient differential subtraction uses the same sample, not magnitudes', () => {
  const report: AnalogReport = { status: 'completed', correlation_id: 'dc', times: [0, 1], warnings: [], netlist: '',
    pin_nodes: { 'R1:0': 'n1', 'R1:1': 'n2' }, traces: [{ name: 'V:n1', unit: 'V', values: [-5, 5] }, { name: 'V:n2', unit: 'V', values: [1, 3] }] };
  assert.deepEqual(probeSignal(report, { kind: 'differential', first: { part: 'R1', terminal: 0 }, second: { part: 'R1', terminal: 1 } })?.real, [-6, 2]);
  assert.equal(voltageScale(report), 5);
  assert.equal(tintedVoltage(5, 5), 'rgb(245,221,160)');
  assert.equal(tintedVoltage(-5, 5), 'rgb(158,205,230)');
  assert.equal(tintedVoltage(0, 5), 'rgb(216,181,146)');
  assert.equal(voltageScale(ac), 0);
});

test('all AC examples are editable versioned circuits with valid component terminal identities', () => {
  for (const kind of ['R', 'C', 'L'] as const) {
    const circuit = sineExample(kind);
    assert.deepEqual(parseSchematic(JSON.stringify({ version: 2, circuit })), circuit);
    assert.ok(circuit.parts.some(part => part.kind === 'SIN'));
    assert.ok(circuit.parts.some(part => part.kind === kind && part.id !== 'R1'));
    assert.ok(circuit.wires.every(wire => circuit.parts.some(part => part.id === wire.a.part) && circuit.parts.some(part => part.id === wire.b.part)));
  }
});

test('one net label avoids symbols, neighboring labels and wire segments and remains inside fit bounds', () => {
  const schematic = starterCircuit();
  const report: AnalogReport = { status: 'completed', correlation_id: 'layout', times: [0, 1], traces: [], warnings: [], netlist: '',
    pin_nodes: { 'V1:0': 'n1', 'R1:0': 'n1', 'R1:1': 'n2', 'C1:0': 'n2', 'V1:1': '0', 'C1:1': '0', 'G1:0': '0' } };
  const labels = nodeLabels(schematic.parts, report, schematic.wires);
  assert.equal(labels.length, 3);
  const wires = wireBoxes(schematic.parts, schematic.wires);
  const [left, top, width, height] = observationViewBox(schematic.parts, labels).split(' ').map(Number);
  for (const label of labels) {
    assert.ok(wires.every(wire => !overlaps(label.box, wire)));
    assert.ok(labels.every(other => label.node === other.node || !overlaps(label.box, other.box)));
    assert.ok(label.box.x >= left && label.box.y >= top && label.box.x + label.box.width <= left + width && label.box.y + label.box.height <= top + height);
  }
});

test('analysis failures surface specific validation without reflecting submitted input', () => {
  assert.equal(analysisFailureMessage({ detail: [{ msg: 'Choose 2–1000 points', input: 'private input' }] }), 'Choose 2–1000 points');
  assert.equal(analysisFailureMessage({ detail: 'Worker busy' }), 'Worker busy');
  assert.match(analysisFailureMessage({ detail: [{ input: 'private input' }] }), /Check/);
});
