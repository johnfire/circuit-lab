import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('public landing explains the preview and links to account creation', async ({ page }) => {
  await page.goto('/landing.html');
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
