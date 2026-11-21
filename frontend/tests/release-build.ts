import assert from 'node:assert/strict';

/** Local fixtures name their build explicitly; staging must identify the exact revision. */
export function assertReleaseBuild(health: { status: string; build_id: string }, expectedBuild?: string): void {
  assert.equal(health.status, 'ok');
  if (expectedBuild) assert.equal(health.build_id, expectedBuild);
  else assert.match(health.build_id, /^[a-f0-9]{40}$/);
}
