import { expect, test, type Browser, type BrowserContext, type Page, type APIRequestContext } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';

const origin = 'https://127.0.0.1:8447';
const identity = 'http://127.0.0.1:8104/auth';
const mailbox = 'http://127.0.0.1:8056/api/v1';

async function localBrowser(browser: Browser, language: string): Promise<BrowserContext> {
  const context = await browser.newContext({ locale: language, ignoreHTTPSErrors: true });
  await context.route('https://stats.christopherrehm.de/**', route => route.abort());
  return context;
}

async function adminHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  const settings = Object.fromEntries((await readFile('../deploy/identity-test.env', 'utf8')).split('\n')
    .filter(line => line && !line.startsWith('#')).map(line => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1)]));
  const response = await request.post(identity + '/realms/master/protocol/openid-connect/token', {
    form: { client_id: 'admin-cli', grant_type: 'password', username: 'circuit-bootstrap', password: settings.CIRCUIT_IDENTITY_ADMIN_PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  return { Authorization: 'Bearer ' + (await response.json()).access_token, 'X-Forwarded-Proto': 'https' };
}

async function accountLocale(request: APIRequestContext, email: string): Promise<string[] | undefined> {
  const response = await request.get(identity + '/admin/realms/circuit-lab/users', {
    headers: await adminHeaders(request), params: { email, exact: 'true' },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json())[0]?.attributes?.locale;
}

async function latestMail(request: APIRequestContext, email: string, expected: number) {
  let message: { Subject: string; Text: string; HTML: string } | undefined;
  await expect(async () => {
    const search = await request.get(mailbox + '/search', { params: { query: 'to:' + email } });
    expect(search.ok()).toBeTruthy();
    const inbox = await search.json() as { messages: { ID: string }[] };
    expect(inbox.messages).toHaveLength(expected);
    const response = await request.get(mailbox + '/message/' + inbox.messages[0].ID);
    message = await response.json();
  }).toPass({ timeout: 20000 });
  if (!message) throw new Error('Expected a captured test email');
  return message;
}

function checkMailLanguage(message: { Subject: string; Text: string; HTML: string }, language: string, reset = false) {
  const expected = language === 'de' ? /bestätig|verifizier|Passwort/i : /verify|verification|password/i;
  expect(message.Subject).toMatch(expected);
  const body = reset ? (language === 'de' ? 'Es wurde eine Änderung der Zugangsdaten' : "Someone just requested to change your Circuit Lab account's credentials.") : expected;
  expect(message.Text).toMatch(body);
  expect(message.HTML.replaceAll('&#39;', "'")).toMatch(body);
  expect(message.HTML).toContain('lang="' + language + '"');
}

async function register(page: Page, language: string, email: string) {
  await page.goto(origin + '/');
  await expect(page.locator('html')).toHaveAttribute('lang', language);
  await page.getByRole('link', { name: language === 'de' ? 'Konto erstellen' : 'Create your account', exact: true }).click();
  await expect(page).toHaveURL(/\/login-actions\/registration/);
  await page.locator('#firstName').fill('Locale');
  await page.locator('#lastName').fill('Fixture');
  await page.locator('#email').fill(email);
  await page.locator('#kc-register-form [type=submit]').click();
  await expect(page.locator('html')).toHaveAttribute('lang', language);
  await page.locator('#password-new').fill('Locale-' + randomUUID());
  await page.locator('#password-confirm').fill(await page.locator('#password-new').inputValue());
  await page.locator('form [type=submit]').click();
  await expect(page.locator('html')).toHaveAttribute('lang', language);
  await expect(page.getByText(email, { exact: false }).first()).toBeVisible();
}

for (const language of ['de', 'en']) {
  test(language + ': real signup, mail, workbench selection, account and password reset', async ({ browser, request }) => {
    const context = await localBrowser(browser, language === 'de' ? 'de-DE' : 'en-GB');
    const page = await context.newPage();
    const email = 'locale-' + randomUUID() + '@example.invalid';
    await register(page, language, email);
    const mail = await latestMail(request, email, 1);
    checkMailLanguage(mail, language);
    const link = mail.Text.match(/https:\/\/[^\s<>]+\/login-actions\/action-token\?[^\s<>]+/)?.[0];
    expect(link).toBeTruthy();
    await delay(1100);
    await page.goto(link!);
    const continuation = page.getByRole('link', { name: /proceed|fortfahren|weiter/i });
    const workbench = page.getByRole('heading', { name: language === 'de' ? 'Sensorspannungsteiler' : 'Sensor voltage divider', exact: true });
    await expect(workbench.or(continuation)).toBeVisible();
    if (await continuation.isVisible()) await continuation.click();
    await expect(workbench).toBeVisible();
    await expect.poll(() => accountLocale(request, email)).toEqual([language]);
    const alternate = language === 'de' ? 'en' : 'de';
    await page.getByLabel(language === 'de' ? 'Sprache' : 'Language').selectOption(alternate);
    await expect.poll(() => accountLocale(request, email)).toEqual([alternate]);
    await page.getByRole('link', { name: alternate === 'de' ? 'Konto & Sicherheit' : 'Account & security' }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', alternate);
    await expect(page.getByLabel(alternate === 'de' ? 'Vorname' : 'First name', { exact: false })).toHaveValue('Locale');
    await expect(page).toHaveTitle(alternate === 'de' ? 'Circuit Lab — Konto' : 'Circuit Lab — Account');
    await expect(page.locator('meta[name=description]')).toHaveAttribute('content', alternate === 'de'
      ? 'Verwalte dein Circuit-Lab-Konto und deine Sicherheitseinstellungen.' : 'Manage your Circuit Lab account and security settings.');
    await context.close();
    const resetContext = await localBrowser(browser, alternate);
    const reset = await resetContext.newPage();
    await reset.goto(origin + '/');
    await reset.getByRole('link', { name: alternate === 'de' ? 'Anmelden' : 'Sign in', exact: true }).click();
    await expect(reset).toHaveURL(/\/login-actions\/authenticate/);
    await reset.getByRole('link', { name: /Forgot Password|Passwort vergessen/i }).click();
    await expect(reset.locator('html')).toHaveAttribute('lang', alternate);
    await reset.locator('#username').fill(email);
    await reset.locator('form [type=submit]').click();
    const resetMail = await latestMail(request, email, 2);
    checkMailLanguage(resetMail, alternate, true);
    const resetLink = resetMail.Text.match(/https:\/\/[^\s<>]+\/login-actions\/action-token\?[^\s<>]+/)?.[0];
    expect(resetLink).toBeTruthy();
    await reset.goto(resetLink!);
    await expect(reset.locator('html')).toHaveAttribute('lang', alternate);
    await reset.locator('#password-new').fill('Reset-' + randomUUID());
    await reset.locator('#password-confirm').fill(await reset.locator('#password-new').inputValue());
    await reset.locator('form [type=submit]').click();
    await expect(reset.locator('html')).toHaveAttribute('lang', alternate);
    await expect(reset.locator('#password-new')).toHaveCount(0);
    await resetContext.close();
  });
}
