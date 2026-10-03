import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('public landing explains the preview and links to account creation', async ({ page }) => {
  await page.goto('/landing.html');
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(32, 8, 8)');
  await expect(page.locator('html')).toHaveCSS('color', 'rgb(216, 181, 146)');
  await expect(page.locator('h1')).toHaveCSS('color', 'rgb(243, 205, 104)');
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
    'href', '/oauth2/start?rd=%2Fworkbench&prompt=create',
  );
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
    'href', '/oauth2/start?rd=%2Fworkbench',
  );
  await expect(page.getByText('Early preview · No paid plans yet')).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
