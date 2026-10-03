import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const COLLECTOR = 'https://stats.christopherrehm.de/api/send';
const TRACKER = 'https://stats.christopherrehm.de/script.js';
const template = readFileSync('../deploy/apache-oidc.conf.template', 'utf8');
const landingPolicy = template.match(/Content-Security-Policy "([^"]+)"/)![1];

test('landing filter loads before tracker and sends only anonymous canonical pageviews', async ({ page }) => {
  let captured: unknown;
  await page.route('**/landing.html*', async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, headers: {
      ...response.headers(), 'content-security-policy': landingPolicy,
    } });
  });
  await page.route(COLLECTOR, async (route) => {
    captured = route.request().postDataJSON();
    await route.fulfill({ json: { cache: 'test-only' } });
  });
  await page.route(TRACKER, (route) => route.fulfill({
    contentType: 'application/javascript',
    body: `const tracker = document.currentScript;
      const payload = window[tracker.dataset.beforeSend]('event', {
        url: 'https://circuit-lab.christopherrehm.de/?token=private#private',
        referrer: 'https://example.com/account/private?token=private',
        language: 'en-US', screen: '390x844', data: { email: 'private@example.com' }
      });
      if (payload) fetch('${COLLECTOR}', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type:'event', payload})});`,
  }));
  await page.goto('/landing.html?token=private#inside');
  await expect.poll(() => captured).toEqual({
    type: 'event',
    payload: {
      website: 'c85d3632-ce92-4753-9505-5be8c9ca13c4',
      hostname: 'circuit-lab.christopherrehm.de', language: 'en-US', screen: '390x844',
      title: 'Circuit Lab', url: 'https://circuit-lab.christopherrehm.de/',
      referrer: 'https://example.com',
    },
  });
});

test('signup links remain usable when analytics is blocked', async ({ page }) => {
  await page.route(TRACKER, (route) => route.abort());
  await page.goto('/landing.html');
  await expect(page.getByRole('heading', { name: /Good circuits start/ })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Create your account' })).toHaveAttribute(
    'href', '/oauth2/start?rd=%2Fworkbench&prompt=create',
  );
});

test('workbench never loads landing analytics', async ({ page }) => {
  const analyticsRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('stats.christopherrehm.de')
      || request.url().includes('landing-analytics.js')) analyticsRequests.push(request.url());
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Sensor voltage divider' })).toBeVisible();
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByText('Simulation checks passed', { exact: true })).toBeVisible();
  expect(analyticsRequests).toEqual([]);
});
