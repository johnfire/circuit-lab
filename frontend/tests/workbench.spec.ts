import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('simulate, change values, inspect failed checks, and export', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/favicon.svg');
  await expect(page.getByRole('heading', { name: 'Sensor voltage divider' })).toBeVisible();
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByText('Simulation checks passed', { exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Voltage waveforms from ngspice' })).toBeVisible();
  await page.locator('#parameter-R1').fill('1000');
  await expect(page.getByText('Parameters changed · rerun required')).toBeVisible();
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByText('Some checks failed')).toBeVisible();
  await page.getByRole('button', { name: 'Verification checks' }).click();
  await expect(page.getByText('Output fits 3.3 V ADC range')).toBeVisible();
  await expect(page.getByText('FAIL', { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export report' }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('voltage_divider-report.json');
  await page.getByRole('button', { name: 'PWM to analog' }).click();
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByText('Simulation checks passed', { exact: true })).toBeVisible();
  await page.getByLabel('Waveform zoom').selectOption('16');
  await expect(page.getByText('Generic/ideal models.', { exact: false })).toBeVisible();
});

test('accessible desktop and mobile workbench', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(32, 8, 8)');
  await expect(page.locator('html')).toHaveCSS('color', 'rgb(216, 181, 146)');
  await expect(page.locator('h1')).toHaveCSS('color', 'rgb(243, 205, 104)');
  await page.getByRole('button', { name: 'Run simulation' }).click();
  await expect(page.getByText('Simulation checks passed', { exact: true })).toBeVisible();
  const desktop = await new AxeBuilder({ page }).analyze();
  expect(desktop.violations).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await new AxeBuilder({ page }).analyze();
  expect(mobile.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
