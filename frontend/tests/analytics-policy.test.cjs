const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const browser = { location: { origin: 'https://circuit-lab.christopherrehm.de' } };
vm.runInNewContext(readFileSync(path.join(__dirname, '../public/landing-analytics.js'), 'utf8'),
  { window: browser, URL });
const filterPageview = browser.filterCircuitLabPageview;
const visit = {
  url: 'https://circuit-lab.christopherrehm.de/?token=private#account',
  referrer: 'https://example.com/accounts/private?token=private#private',
  website: 'wrong-website',
  language: 'en-US',
  screen: '390x844',
  title: 'Private account title',
  data: { email: 'private@example.com' },
};

test('landing pageviews allow only anonymous fields and origin-only referrers', () => {
  const anonymous = JSON.parse(JSON.stringify(filterPageview('event', visit)));
  assert.deepEqual(anonymous, {
    website: 'c85d3632-ce92-4753-9505-5be8c9ca13c4',
    hostname: 'circuit-lab.christopherrehm.de',
    language: 'en-US',
    screen: '390x844',
    title: 'Circuit Lab',
    url: 'https://circuit-lab.christopherrehm.de/',
    referrer: 'https://example.com',
  });
});

test('landing alias and fragments canonicalize to one page', () => {
  const anonymous = filterPageview('event', { ...visit, url: '/landing.html?code=private#inside' });
  assert.equal(anonymous.url, 'https://circuit-lab.christopherrehm.de/');
});

test('local hosts, other domains and account routes are never tracked', () => {
  for (const url of ['http://localhost:8010/', 'https://example.com/',
    '/workbench', '/oauth2/callback?code=private', '/auth/realms/circuit-lab/account', '/api/me']) {
    assert.equal(filterPageview('event', { ...visit, url }), false);
  }
});

test('identification and custom events are rejected', () => {
  assert.equal(filterPageview('identify', visit), false);
  assert.equal(filterPageview('event', { ...visit, name: 'signup' }), false);
  assert.equal(filterPageview('event', { ...visit, id: 'account-id' }), false);
});

test('same-site and non-web referrers are removed', () => {
  for (const referrer of ['', 'https://circuit-lab.christopherrehm.de/workbench',
    'mailto:private@example.com', 'javascript:private']) {
    assert.equal(filterPageview('event', { ...visit, referrer }).referrer, '');
  }
});

test('malformed inputs fail closed without throwing', () => {
  for (const payload of [null, {}, { ...visit, url: 'http://[' },
    { ...visit, referrer: 'http://[' }]) {
    assert.equal(filterPageview('event', payload), false);
  }
});
