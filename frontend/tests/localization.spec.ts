import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('German and English', () => {
  test.use({ locale: 'de-DE' });

  test('landing follows browser language, remembers choice and carries it to sign-in', async ({ page }) => {
    await page.goto('/landing.html');
    await expect(page.locator('html')).toHaveAttribute('lang', 'de');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Gute Schaltungen beginnenmit guten Fragen.');
    await page.screenshot({ path: '/tmp/circuit-lab-localization-review/landing-de.png' });
    await page.getByLabel('Sprache').selectOption('en');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/oauth2/start?rd=%2Fworkbench&ui_locales=en&kc_locale=en');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await page.screenshot({ path: '/tmp/circuit-lab-localization-review/landing-en.png' });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  });

  test('switching a working circuit preserves graph, input values and simulation evidence', async ({ page }) => {
    await page.goto('/workbench?mode=build');
    await expect(page.getByRole('heading', { name: 'Deine Schaltung, Zeitpunkt für Zeitpunkt.' })).toBeVisible();
    await page.getByRole('button', { name: 'Schaltung simulieren', exact: true }).click();
    await expect(page.getByText(/Simulation abgeschlossen und zur Prüfung pausiert/)).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: '/tmp/circuit-lab-localization-review/workbench-de.png' });
    await page.locator('.grid-panel').screenshot({ path: '/tmp/circuit-lab-localization-review/circuit-de.png' });
    await expect(page.locator('.schematic-grid .terminal')).toHaveCount(7);
    const references = await page.locator('.schematic-part').count();
    const runId = (await page.locator('.trace-id').textContent())?.match(/[a-f0-9-]{36}/)?.[0];
    expect(runId).toMatch(/^[a-f0-9-]{36}$/);
    const draftBefore = await page.evaluate(() => ({ ...localStorage }));
    await page.getByLabel('Sprache').selectOption('en');
    await expect(page.getByRole('heading', { name: 'Your circuit, one instant at a time.' })).toBeVisible();
    await expect(page.getByText(/Simulation complete. Paused for inspection/)).toBeVisible();
    expect(await page.locator('.schematic-part').count()).toBe(references);
    await expect(page.locator('.trace-id')).toContainText(runId!);
    expect(await page.evaluate(() => ({ ...localStorage }))).toEqual(draftBefore);
    await expect(page.getByRole('button', { name: 'Resistor', exact: true })).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: '/tmp/circuit-lab-localization-review/workbench-en.png' });
    const geometry = await page.locator('.schematic-part .symbol').evaluateAll(parts => parts.map(part => part.getAttribute('transform')));
    expect(geometry.length).toBe(references);
    expect(geometry[0]).toMatch(/^translate\(/);
    await page.locator('html').evaluate(element => { element.dir = 'rtl'; });
    expect(await page.locator('.schematic-grid').evaluate(element => getComputedStyle(element).direction)).toBe('ltr');
    expect(await page.locator('.schematic-part .symbol').evaluateAll(parts => parts.map(part => part.getAttribute('transform')))).toEqual(geometry);
    await page.getByLabel('Language').selectOption('de');
    await expect(page.getByRole('button', { name: 'Widerstand', exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    const selector = await page.getByLabel('Sprache').boundingBox();
    const masthead = await page.locator('.masthead').boundingBox();
    expect(selector && masthead && selector.y + selector.height <= masthead.y + masthead.height).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: '/tmp/circuit-lab-localization-review/workbench-de-mobile.png' });
  });
});

test('unsupported browser language falls back to English', async ({ browser }) => {
  const context = await browser.newContext({ locale: 'pl-PL' });
  const page = await context.newPage();
  await page.goto('/workbench');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('heading', { name: 'Sensor voltage divider', exact: true })).toBeVisible();
  await context.close();
});


test('blocked browser storage still allows language switching and decimal entry stays numeric', async ({ browser }) => {
  const context = await browser.newContext({ locale: 'de-DE' });
  await context.addInitScript(() => {
    Object.defineProperty(document, 'cookie', { get() { throw new Error('Storage blocked'); }, set() { throw new Error('Storage blocked'); } });
  });
  const page = await context.newPage();
  await page.goto('/landing.html');
  await expect(page.locator('html')).toHaveAttribute('lang', 'de');
  await page.getByLabel('Sprache').selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.goto('/workbench');
  await expect(page.locator('html')).toHaveAttribute('lang', 'de');
  const resistor = page.locator('#parameter-R1');
  await resistor.fill('1234.5');
  await page.getByLabel('Sprache').selectOption('en');
  await expect(resistor).toHaveValue('1234.5');
  const submitted = page.waitForRequest(request => request.url().endsWith('/api/circuits/voltage_divider/simulate'));
  await page.getByRole('button', { name: 'Run simulation', exact: true }).click();
  expect((await submitted).postDataJSON().parameters.R1).toBe(1234.5);
  await context.close();
});
