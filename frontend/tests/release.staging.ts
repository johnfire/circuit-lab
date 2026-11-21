import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { assertReleaseBuild } from './release-build.ts';
import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';

const identity = '/auth/realms/circuit-lab';
const mailbox = '/_stage/mail/api/v1';

async function signup(page: Page, email: string, language: string) {
  await page.goto('/');
  await page.getByLabel(/Sprache|Language/).selectOption(language);
  await page.getByRole('link', { name: language === 'de' ? 'Konto erstellen' : 'Create your account', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', language);
  const form = page.locator('#kc-register-form');
  await form.locator('#firstName').fill('Release');
  await form.locator('#lastName').fill('Fixture');
  await form.locator('#email').fill(email);
  await form.locator('[type=submit]').click();
  await expect(page.getByRole('heading', { name: language === 'de' ? 'Passwort aktualisieren' : 'Update password' })).toBeVisible();
  const password = 'Stage-' + randomUUID();
  const passwordForm = page.locator('form').filter({ has: page.locator('#password-new') });
  await passwordForm.locator('#password-new').fill(password);
  await passwordForm.locator('#password-confirm').fill(password);
  await passwordForm.locator('[type=submit]').click();
  await expect(page.getByRole('heading', { name: language === 'de' ? 'E-Mail verifizieren' : 'Email verification' })).toBeVisible();
}

async function verificationLink(request: APIRequestContext, email: string, origin: string, language: string) {
  let link: URL | undefined;
  await expect(async () => {
    const search = await request.get(mailbox + '/search', { params: { query: 'to:' + email } });
    expect(search.ok()).toBeTruthy();
    const inbox = await search.json() as { messages: { ID: string }[] };
    expect(inbox.messages).toHaveLength(1);
    const message = await request.get(mailbox + '/message/' + inbox.messages[0].ID);
    expect(message.ok()).toBeTruthy();
    const mail = await message.json() as { Text: string; HTML: string; Subject: string };
    const expected = language === 'de' ? /bestätig|verifizier/i : /verify|verification/i;
    expect(mail.Subject).toMatch(expected);
    expect(mail.Text).toMatch(expected);
    expect(mail.HTML).toMatch(expected);
    const url = mail.Text.match(/https:\/\/[^\s<>]+\/login-actions\/action-token\?[^\s<>]+/);
    if (!url) throw new Error('Email did not contain the registration verification link');
    link = new URL(url[0]);
    expect(link.origin).toBe(origin);
    expect(link.pathname).toBe(identity + '/login-actions/action-token');
  }).toPass({ timeout: 30_000 });
  if (!link) throw new Error('Registration email did not contain a staging verification link');
  return link.toString();
}

async function verifyWorkbench(page: Page, email: string, language: string) {
  const expectedBuild = process.env.CIRCUIT_EXPECTED_BUILD;
  const health = await page.request.get('/api/health');
  expect(health.ok()).toBeTruthy();
  const build = await health.json() as { status: string; build_id: string };
  assertReleaseBuild(build, expectedBuild);
  await page.getByRole('button', { name: language === 'de' ? 'Simulation starten' : 'Run simulation' }).click();
  await expect(page.getByText(language === 'de' ? 'Simulationsprüfungen bestanden' : 'Simulation checks passed', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: language === 'de' ? 'Schaltung bauen' : 'Build circuit', exact: true }).click();
  await page.getByRole('button', { name: language === 'de' ? 'Neues Projekt speichern' : 'Save new project', exact: true }).click();
  await expect(page.getByText(language === 'de' ? 'Projekt privat gespeichert.' : 'Project saved privately.', { exact: false })).toBeVisible();
  await verifyPcbReview(page, language);
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

async function verifyPcbReview(page: Page, language: string) {
  const german = language === 'de';
  await page.getByRole('button', { name: german ? 'Platinenentwurf erstellen' : 'Generate board draft' }).click();
  await expect(page.getByText(german ? 'Ungerouteter Entwurf:' : 'Unrouted draft:', { exact: false })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole('img', { name: german ? 'Platinenansicht' : 'PCB layer view' })).toBeVisible();
  await page.locator('.pcb-review input[type=file]').setInputFiles('../tests/fixtures/pcb/partially-routed.kicad_pcb');
  await expect(page.getByText(german ? 'Leiterbahnen und Durchkontaktierungen: 1' : 'Tracks and vias: 1',
    { exact: false })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(german ? 'Importierte KiCad-Platine.' : 'Imported KiCad board.', { exact: false })).toBeVisible();
}

for (const language of ['de', 'en']) {
test(language + ': private staging registers, verifies email, simulates, saves, and exports', async ({
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
  await signup(page, email, language);
  const link = await verificationLink(request, email, baseURL, language);
  // Circuit Lab rejects tokens issued in the same second as a password update.
  await delay(1_100);
  await page.goto(link);
  const continuation = page.getByRole('link', { name: /Click here to proceed|Hier klicken.*fortfahren|Klicken Sie hier.*fortzufahren/i });
  const workbench = page.getByRole('heading', { name: language === 'de' ? 'Sensorspannungsteiler' : 'Sensor voltage divider' });
  await expect(workbench.or(continuation)).toBeVisible();
  if (await continuation.isVisible()) await continuation.click();
  await expect(workbench).toBeVisible();
  await verifyWorkbench(page, email, language);
});
}
