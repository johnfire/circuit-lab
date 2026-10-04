import assert from 'node:assert/strict';
import test from 'node:test';
import { contentsFingerprint, syncDecision } from '../src/project-api.ts';
import { starterCircuit } from '../src/schematic-model.ts';
import type { CircuitContents, CircuitSnapshot } from '../src/project-api.ts';

const contents: CircuitContents = { circuit: starterCircuit(), sweep: null };
const binding: CircuitSnapshot = { document: 'test-document', revision: 'first', name: 'private', kind: 'workspace',
  parent: null, actor: 'user:test', reason: 'Created', contents };

test('optional source nulls and JSON property order do not create false unsent edits', () => {
  const normalized = { ...contents, circuit: { ...contents.circuit, parts: contents.circuit.parts.map(part =>
    ({ sine: null, pulse: null, ...part })) } } as CircuitContents;
  assert.equal(contentsFingerprint(normalized), contentsFingerprint(contents));
});

test('server revisions are adopted only when local contents are clean and not simulating', () => {
  const server = { ...binding, revision: 'second' };
  assert.equal(syncDecision(binding, contents, server, false), 'adopt');
  assert.equal(syncDecision(binding, contents, server, true), 'conflict');
  const local = { ...contents, circuit: { ...contents.circuit, timing: { stop: .1, step: .0001 } } };
  assert.equal(syncDecision(binding, local, server, false), 'conflict');
  assert.equal(syncDecision(binding, local, binding, false), 'push');
  assert.equal(syncDecision(binding, local, binding, true), 'none');
  assert.equal(syncDecision(binding, contents, binding, false), 'none');
});
