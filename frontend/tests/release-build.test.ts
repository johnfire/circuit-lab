import assert from 'node:assert/strict';
import test from 'node:test';
import { assertReleaseBuild } from './release-build.ts';

const revision = '9a2263aa9756df815584ac9c35ac0dbe1ab1da68';

test('release build checks reject missing or malformed revision identity', () => {
  assertReleaseBuild({ status: 'ok', build_id: revision });
  assertReleaseBuild({ status: 'ok', build_id: revision }, revision);
  assertReleaseBuild({ status: 'ok', build_id: 'local' }, 'local');
  assert.throws(() => assertReleaseBuild({ status: 'failed', build_id: revision }));
  assert.throws(() => assertReleaseBuild({ status: 'ok', build_id: 'local' }));
  assert.throws(() => assertReleaseBuild({ status: 'ok', build_id: revision }, 'different'));
});
