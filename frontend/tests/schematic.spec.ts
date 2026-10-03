import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('real RC simulation, synchronized readouts, slow playback and electrical invalidation', async ({ page }) => {
  let jobs = 0;
  page.on('request', request => { if (request.url().endsWith('/api/schematic/simulate')) jobs++; });
  await page.goto('/?mode=build');
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toBeVisible();
  await page.getByLabel('Watch from (ms)').fill('11');
  await expect(page.getByLabel('Frame time')).toContainText('11 ms');
  await expect(page.getByRole('row', { name: 'C1 3.16 V 0 V 1.84 mA', exact: true })).toBeVisible();
  await expect(page.locator('.node-reading').filter({ hasText: '3.16 V' })).toHaveCount(2);
  await page.getByRole('button', { name: 'Next frame', exact: true }).click();
  await expect(page.getByLabel('Frame time')).toContainText('11.1 ms');
  await page.getByLabel('Playback rate').selectOption('0.001');
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await expect.poll(async () => Number(await page.getByLabel('Time cursor', { exact: true }).inputValue())).toBeGreaterThan(.0113);
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  expect(jobs).toBe(1);
  await page.getByLabel('Watch from (ms)').fill('0');
  await expect(page.getByLabel('Frame time')).toContainText('0 s');
  await page.getByLabel('Standard value').selectOption('2200');
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toHaveCount(0);
  await expect(page.locator('.node-reading')).toHaveCount(0);
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toBeVisible();
  expect(jobs).toBe(2);
});

test('build a grounded divider from blank using standard parts and explicit keyboard wiring', async ({ page }) => {
  await page.goto('/?mode=build');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'New blank', exact: true }).click();
  for (const name of ['DC source', 'Resistor', 'Resistor', 'Ground']) {
    await page.getByRole('button', { name, exact: true }).click();
    await page.getByRole('button', { name: 'Add to grid', exact: true }).click();
    await page.getByLabel('Place column').fill(String(name === 'DC source' ? 16 : name === 'Ground' ? 28 : 22));
  }
  await page.getByText('Connections (0)', { exact: true }).click();
  const terminals = ['V1:0', 'R1:0', 'R1:1', 'R2:0', 'R2:1', 'G1:0', 'G1:0', 'V1:1'];
  for (let index = 0; index < terminals.length; index++) {
    await page.getByLabel(index % 2 ? 'Connect to terminal' : 'Start wire at terminal').selectOption(terminals[index]);
  }
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('row', { name: 'R2 2.5 V 0 V 2.5 mA', exact: true })).toBeVisible();
  const exported = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export circuit', exact: true }).click();
  expect((await exported).suggestedFilename()).toBe('circuit-lab-schematic.json');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Select R2 1 kΩ', exact: true })).toBeVisible();
});

test('terminal wiring, grid placement, rotation and movement preserve connectivity', async ({ page }) => {
  await page.goto('/?mode=build');
  await page.getByText('Connections (4)', { exact: true }).click();
  await page.getByRole('button', { name: 'Remove wire 1', exact: true }).click();
  await page.getByRole('button', { name: 'V1 terminal 0', exact: true }).click();
  await page.getByRole('button', { name: 'R1 terminal 0', exact: true }).click();
  await page.getByRole('button', { name: 'Rotate 90°', exact: true }).click();
  await page.getByRole('button', { name: 'Move right', exact: true }).click();
  await expect(page.getByLabel('Column', { exact: true })).toHaveValue('18');
  await expect(page.getByText('Rotation: 90°', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toBeVisible();
  await page.getByRole('button', { name: 'Capacitor', exact: true }).click();
  const grid = page.locator('.schematic-grid');
  const bounds = await grid.boundingBox();
  if (!bounds) throw new Error('Grid unavailable');
  await grid.click({ position: { x: bounds.width * .4, y: bounds.height * .2 } });
  await expect(page.getByRole('heading', { name: 'C2 · Capacitor', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('alert')).toContainText('Connect every terminal');
});

test('invalid imported circuits are refused without changing the browser draft', async ({ page }) => {
  await page.goto('/?mode=build');
  await page.getByLabel('Import circuit', { exact: true }).setInputFiles({ name: 'bad.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({ parts: [], wires: [], timing: { stop: .1, step: .001 }, netlist: '.include secret' })) });
  await expect(page.getByRole('alert')).toContainText('Unknown circuit fields');
  await expect(page.getByRole('button', { name: 'Select R1 1 kΩ', exact: true })).toBeVisible();
});

test('analog editor is accessible on desktop and mobile without page overflow', async ({ page }) => {
  await page.goto('/?mode=build');
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  const measurements = page.getByRole('region', { name: 'Scrollable circuit measurements' });
  await expect(measurements).toHaveAttribute('tabindex', '0');
  await measurements.focus();
  await expect(measurements).toBeFocused();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByLabel('Watch from (ms)').fill('11');
  await expect(page.getByLabel('Frame time')).toContainText('11 ms');
});

test('pointer drag snaps a symbol to the grid without invalidating simulation results', async ({ page }) => {
  await page.goto('/?mode=build');
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toBeVisible();
  const hitbox = page.getByRole('button', { name: 'Select R1 1 kΩ', exact: true }).locator('.part-hitbox');
  await hitbox.scrollIntoViewIfNeeded();
  const bounds = await hitbox.boundingBox();
  if (!bounds) throw new Error('Resistor hitbox unavailable');
  const x = bounds.x + bounds.width / 2, y = bounds.y + bounds.height / 2;
  await page.mouse.move(x, y); await page.mouse.down();
  await page.mouse.move(x + bounds.width / 3, y, { steps: 4 }); await page.mouse.up();
  await expect(page.getByLabel('Column', { exact: true })).toHaveValue('18');
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toBeVisible();
  await page.getByRole('button', { name: 'Select R1 1 kΩ', exact: true }).press('ArrowLeft');
  await expect(page.getByLabel('Column', { exact: true })).toHaveValue('17');
});
