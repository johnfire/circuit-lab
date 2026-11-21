import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('public landing explains the preview and links to account creation', async ({ page }) => {
  await page.goto('/landing.html');
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(21, 5, 5)');
  await expect(page.locator('html')).toHaveCSS('color', 'rgb(216, 181, 146)');
  await expect(page.locator('h1')).toHaveCSS('color', 'rgb(245, 221, 160)');
  const theme = await page.request.get('/theme.css');
  expect(theme.status()).toBe(200);
  expect(theme.headers()['content-type']).toContain('text/css');
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/favicon.svg');
  const favicon = await page.request.get('/favicon.svg');
  expect(favicon.status()).toBe(200);
  expect(favicon.headers()['content-type']).toContain('image/svg+xml');
  expect(await favicon.text()).toContain('<title>Circuit Lab</title>');
  await expect(page.getByRole('heading', { name: /Good circuits start/ })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Create your account' })).toHaveAttribute(
    'href', '/oauth2/start?rd=%2Fworkbench&prompt=create&ui_locales=en&kc_locale=en',
  );
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
    'href', '/oauth2/start?rd=%2Fworkbench&ui_locales=en&kc_locale=en',
  );
  await expect(page.getByText('Early preview · No paid plans yet')).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('desktop header controls share a horizontal center in German and English', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto('/landing.html');
  for (const language of ['de', 'en']) {
    await page.locator('#language').selectOption(language);
    const centers = await page.locator('.site-header .brand, .site-header nav > a, .site-header .language-selector > span').evaluateAll(
      elements => elements.map(element => {
        const range = document.createRange();
        range.selectNodeContents(element);
        const bounds = range.getBoundingClientRect();
        return bounds.top + bounds.height / 2;
      }),
    );
    expect(Math.max(...centers) - Math.min(...centers)).toBeLessThan(6);
  }
});
