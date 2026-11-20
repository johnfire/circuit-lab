import assert from 'node:assert/strict';
import test from 'node:test';
import { resolveLocale, readLanguageCookie, languageCookie } from '../src/locale-preference.ts';

test('explicit choice wins, regional browser preferences match in order, English is fallback', () => {
  assert.equal(resolveLocale('de', ['en-US']), 'de');
  assert.equal(resolveLocale('en', ['de-DE']), 'en');
  assert.equal(resolveLocale(null, ['fr-FR', 'de-AT', 'en-GB']), 'de');
  assert.equal(resolveLocale(null, ['en-GB', 'de']), 'en');
  assert.equal(resolveLocale('ar', ['de-DE']), 'de');
  assert.equal(resolveLocale(null, ['ar', 'pl']), 'en');
  assert.equal(resolveLocale(null, []), 'en');
});

test('language cookie is bounded, host-only and rejects unrelated or malformed values', () => {
  assert.equal(readLanguageCookie('other=de; circuit-language=en'), 'en');
  assert.equal(readLanguageCookie('circuit-language=de; other=en'), 'de');
  assert.equal(readLanguageCookie('circuit-language=ar'), null);
  assert.equal(readLanguageCookie('circuit-language=%broken'), null);
  assert.equal(readLanguageCookie('other=de'), null);
  assert.equal(languageCookie('de', true), 'circuit-language=de; Path=/; Max-Age=31536000; SameSite=Lax; Secure');
  assert.equal(languageCookie('en', false), 'circuit-language=en; Path=/; Max-Age=31536000; SameSite=Lax');
});
