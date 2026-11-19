import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';

const identity = '/auth/realms/circuit-lab';
const mailbox = '/_stage/mail/api/v1';

async function signup(page: Page, email: string) {
  await page.goto('/oauth2/start?rd=%2Fworkbench&prompt=create');
  const form = page.locator('#kc-register-form');
  await form.locator('#firstName').fill('Release');
  await form.locator('#lastName').fill('Fixture');
  await form.locator('#email').fill(email);
  await form.locator('[type=submit]').click();
  await expect(page.getByRole('heading', { name: 'Update password' })).toBeVisible();
  const password = 'Stage-' + randomUUID();
  const passwordForm = page.locator('form').filter({ has: page.locator('#password-new') });
  await passwordForm.locator('#password-new').fill(password);
  await passwordForm.locator('#password-confirm').fill(password);
  await passwordForm.locator('[type=submit]').click();
  await expect(page.getByRole('heading', { name: 'Email verification' })).toBeVisible();
}

async function verificationLink(request: APIRequestContext, email: string, origin: string) {
  let link: URL | undefined;
  await expect(async () => {
    const search = await request.get(mailbox + '/search', { params: { query: 'to:' + email } });
    expect(search.ok()).toBeTruthy();
    const inbox = await search.json() as { messages: { ID: string }[] };
    expect(inbox.messages).toHaveLength(1);
    const message = await request.get(mailbox + '/message/' + inbox.messages[0].ID);
    expect(message.ok()).toBeTruthy();
    const mail = await message.json() as { Text: string };
    const url = mail.Text.match(/https:\/\/[^\s<>]+\/login-actions\/action-token\?[^\s<>]+/);
    if (!url) throw new Error('Email did not contain the registration verification link');
    link = new URL(url[0]);
    expect(link.origin).toBe(origin);
    expect(link.pathname).toBe(identity + '/login-actions/action-token');
  }).toPass({ timeout: 30_000 });
  if (!link) throw new Error('Registration email did not contain a staging verification link');
  return link.toString();
}

async function verifyWorkbench(page: Page, email: string) {
  const expectedBuild = process.env.CIRCUIT_EXPECTED_BUILD;
  const health = await page.request.get('/api/health');
  expect(health.ok()).toBeTruthy();
  const build = await health.json() as { status: string; build_id: string };
  expect(build).toMatchObject({ status: 'ok', build_id: expectedBuild || /^[a-f0-9]{40}$/ });
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByText('Simulation checks passed', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Build circuit', exact: true }).click();
  await page.getByRole('button', { name: 'Save new project', exact: true }).click();
  await expect(page.getByText('Project saved privately.', { exact: false })).toBeVisible();
  const exported = await page.request.get('/api/account/export');
  expect(exported.ok()).toBeTruthy();
  expect(await exported.json()).toMatchObject({
    profile: { email },
    simulation_events: expect.arrayContaining([
      expect.objectContaining({ actor: expect.stringMatching(/^user:/) }),
    ]),
    saved_projects: { documents: [expect.anything()] },
  });
}

test('private staging registers, verifies email, simulates, saves, and exports', async ({
  page, request, baseURL,
}) => {
  if (!baseURL) throw new Error('Expected the staging site URL');
  const email = `release-${randomUUID()}@example.invalid`;
  const anonymousWorkbench = await request.get('/workbench', { maxRedirects: 0 });
  expect(anonymousWorkbench.status()).toBe(302);
  expect((await request.get('/auth/admin/', { maxRedirects: 0 })).status()).toBe(403);
  const discovery = await request.get('/.well-known/oauth-protected-resource/mcp');
  expect(discovery.ok()).toBeTruthy();
  expect(await discovery.json()).toMatchObject({
    resource: baseURL + '/mcp', authorization_servers: [baseURL + identity],
  });
  await signup(page, email);
  const link = await verificationLink(request, email, baseURL);
  // Circuit Lab rejects tokens issued in the same second as a password update.
  await delay(1_100);
  await page.goto(link);
  const continuation = page.getByRole('link', { name: 'Click here to proceed' });
  const workbench = page.getByRole('heading', { name: 'Sensor voltage divider' });
  await expect(workbench.or(continuation)).toBeVisible();
  if (await continuation.isVisible()) await continuation.click();
  await expect(workbench).toBeVisible();
  await verifyWorkbench(page, email);
});
