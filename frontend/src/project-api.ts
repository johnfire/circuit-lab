import { parseSchematic } from './schematic-files.ts';
import { analysisFailureMessage } from './schematic-api.ts';
import type { Schematic, Sweep } from './schematic-types';

export interface CircuitContents { circuit: Schematic; sweep: Sweep | null }
export interface CircuitSnapshot {
  document: string; revision: string; name: string; kind: 'project' | 'workspace';
  parent: string | null; actor: string; reason: string; contents: CircuitContents;
}
export interface ProjectSummary { id: string; name: string; kind: string; revision: string }
export interface RevisionSummary { revision: string; actor: string; reason: string; created_at: string }
export interface SharingStatus { enabled: boolean; clients: string[]; endpoint: string }

export function contentsFingerprint(contents: CircuitContents): string {
  const normalize = (value: unknown): unknown => Array.isArray(value) ? value.map(normalize)
    : typeof value === 'object' && value !== null ? Object.fromEntries(Object.entries(value).sort(([first], [second]) => first.localeCompare(second))
      .map(([key, nested]) => [key, normalize(nested)])) : value;
  const circuit = { ...contents.circuit, parts: contents.circuit.parts.map(part => ({ ...part,
    pulse: part.pulse ?? null, sine: part.sine ?? null })) };
  return JSON.stringify(normalize({ ...contents, circuit }));
}

export function syncDecision(binding: CircuitSnapshot, local: CircuitContents, server: CircuitSnapshot, running: boolean) {
  const dirty = contentsFingerprint(local) !== contentsFingerprint(binding.contents);
  if (server.revision !== binding.revision) return dirty || running ? 'conflict' : 'adopt';
  return dirty && !running ? 'push' : 'none';
}

export async function projectRequest<T>(path: string, submitted?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch('/api/projects' + path, { method: submitted === undefined ? 'GET' : 'POST',
    headers: submitted === undefined ? {} : { 'Content-Type': 'application/json' },
    body: submitted === undefined ? undefined : JSON.stringify(submitted), cache: 'no-store',
    signal: signal ?? AbortSignal.timeout(10000) });
  const decoded: unknown = await response.json();
  if (!response.ok) throw new Error(analysisFailureMessage(decoded));
  return decoded as T;
}

export function parseSnapshot(snapshot: CircuitSnapshot): CircuitSnapshot {
  if (!snapshot || !snapshot.contents || typeof snapshot.revision !== 'string' || typeof snapshot.document !== 'string') {
    throw new Error('Invalid server snapshot; your local draft is unchanged.');
  }
  return { ...snapshot, contents: { circuit: parseSchematic(JSON.stringify(snapshot.contents.circuit)), sweep: snapshot.contents.sweep } };
}

export function revisionCommand(snapshot: CircuitSnapshot, reason: string) {
  return { expected_revision: snapshot.revision, idempotency_key: crypto.randomUUID(), reason };
}
