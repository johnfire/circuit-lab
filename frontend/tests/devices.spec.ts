import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

type Connection = [string, number, string, number];

function relayDriver(flyback: boolean) {
  const parts: Record<string, unknown>[] = [
    { id: 'VG', kind: 'PULSE', value: 3.3, x: 4, y: 12, rotation: 90, pulse: { period: .02, width: .01, delay: .001 } },
    { id: 'RG', kind: 'R', value: 100, x: 10, y: 10, rotation: 0 },
    { id: 'RPD', kind: 'R', value: 100000, x: 14, y: 16, rotation: 90 },
    { id: 'Q1', kind: 'NMOS', device: 'irlz44n', value: 0, x: 20, y: 12, rotation: 0 },
    { id: 'RC', kind: 'R', value: 400, x: 24, y: 4, rotation: 90 },
    { id: 'LC', kind: 'L', value: .1, x: 24, y: 8, rotation: 90 },
    { id: 'VS', kind: 'V', value: 12, x: 32, y: 10, rotation: 90 },
    { id: 'G1', kind: 'GND', value: 0, x: 18, y: 20, rotation: 0 },
  ];
  const connections: Connection[] = [['VG', 0, 'RG', 0], ['RG', 1, 'Q1', 1], ['RPD', 0, 'Q1', 1], ['RPD', 1, 'G1', 0],
    ['Q1', 2, 'G1', 0], ['VG', 1, 'G1', 0], ['VS', 1, 'G1', 0], ['VS', 0, 'RC', 0], ['RC', 1, 'LC', 0], ['LC', 1, 'Q1', 0]];
  if (flyback) {
    parts.push({ id: 'D1', kind: 'D', device: '1n4148', value: 0, x: 29, y: 6, rotation: 270 });
    connections.push(['D1', 0, 'Q1', 0], ['D1', 1, 'VS', 0]);
  }
  return { version: 2, circuit: { parts, timing: { stop: .04, step: .00002 },
    wires: connections.map(([a, ta, b, tb]) => ({ a: { part: a, terminal: ta }, b: { part: b, terminal: tb } })) } };
}

async function importAndSimulate(page: Page, flyback: boolean) {
  await page.getByLabel('Import circuit', { exact: true }).setInputFiles({ name: 'relay.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(relayDriver(flyback))) });
  await expect(page.getByRole('button', { name: 'Select Q1 IRLZ44N', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('heading', { name: 'Watch the circuit' })).toBeVisible({ timeout: 15000 });
}

test('relay driver: library parts pass their ratings with a flyback diode and fail without one', async ({ page }) => {
  await page.goto('/?mode=build');
  await importAndSimulate(page, true);
  const ratings = page.getByRole('region', { name: /Part ratings/ });
  await expect(ratings).toContainText('All 7 within limits');
  await expect(ratings).toContainText('Draft part: limit unconfirmed');
  await expect(page.getByRole('row', { name: /^Q1 D .* G .* S 0 V/ })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await importAndSimulate(page, false);
  await expect(ratings).toContainText('1 of 4 exceeded');
  await expect(ratings.locator('.check.fail')).toContainText('Drain–source voltage');
  await expect(ratings.locator('.check.fail')).toContainText('EXCEEDS LIMIT');
});

test('a placed transistor offers library parts of its kind and shows their trust level', async ({ page }) => {
  await page.goto('/?mode=build');
  await page.getByRole('button', { name: 'N-MOSFET', exact: true }).click();
  await page.getByRole('button', { name: 'Add to grid', exact: true }).click();
  await page.getByRole('button', { name: /^Select Q1 / }).click();
  const choice = page.getByLabel('Library part');
  await choice.selectOption('irlz44n');
  await expect(page.getByRole('button', { name: 'Select Q1 IRLZ44N', exact: true })).toBeVisible();
  await expect(page.getByText('Draft', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Q1 terminal gate', exact: true })).toBeVisible();
  expect(await choice.locator('option').allTextContents()).not.toContain(expect.stringMatching(/1N4148/));
});

test('a 7805 dropping 12 V at 0.5 A fails its power rating in the browser', async ({ page }) => {
  await page.goto('/?mode=build');
  const circuit = { version: 2, circuit: { timing: { stop: .001, step: .00001 }, parts: [
    { id: 'VIN', kind: 'V', value: 12, x: 4, y: 10, rotation: 90 },
    { id: 'U1', kind: 'REG', device: 'lm7805', value: 0, x: 14, y: 8, rotation: 0 },
    { id: 'RL', kind: 'R', value: 10, x: 24, y: 10, rotation: 90 },
    { id: 'G1', kind: 'GND', value: 0, x: 14, y: 18, rotation: 0 }],
  wires: [['VIN', 0, 'U1', 1], ['U1', 0, 'RL', 0], ['U1', 2, 'G1', 0], ['RL', 1, 'G1', 0], ['VIN', 1, 'G1', 0]]
    .map(([a, ta, b, tb]) => ({ a: { part: a, terminal: ta }, b: { part: b, terminal: tb } })) } };
  await page.getByLabel('Import circuit', { exact: true }).setInputFiles({ name: 'regulator.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(circuit)) });
  await expect(page.getByRole('button', { name: 'Select U1 LM7805', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'U1 terminal ground_or_adjust', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  const ratings = page.getByRole('region', { name: /Part ratings/ });
  await expect(ratings).toContainText('1 of 3 exceeded', { timeout: 15000 });
  await expect(ratings.locator('.check.fail')).toContainText('Power dissipation');
  await expect(page.getByRole('row', { name: /^U1 OUT 5 V IN 12 V G\/A 0 V/ })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('5 V into a Raspberry Pi pin is flagged, and the pinout shows where to wire', async ({ page }) => {
  await page.goto('/?mode=build');
  const circuit = { version: 2, circuit: { timing: { stop: .001, step: .00001 }, parts: [
    { id: 'P1', kind: 'PIN', value: 0, x: 4, y: 10, rotation: 0, board_pin: { board: 'raspberry_pi_4', pin: '11', mode: 'input' } },
    { id: 'R1', kind: 'R', value: 1000, x: 14, y: 8, rotation: 0 },
    { id: 'VS', kind: 'V', value: 5, x: 24, y: 10, rotation: 90 },
    { id: 'G1', kind: 'GND', value: 0, x: 16, y: 18, rotation: 0 }],
  wires: [['P1', 0, 'R1', 0], ['R1', 1, 'VS', 0], ['VS', 1, 'G1', 0]]
    .map(([a, ta, b, tb]) => ({ a: { part: a, terminal: ta }, b: { part: b, terminal: tb } })) } };
  await page.getByLabel('Import circuit', { exact: true }).setInputFiles({ name: 'pi.json', mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(circuit)) });
  await expect(page.getByRole('button', { name: 'Select P1 GPIO17', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  const ratings = page.getByRole('region', { name: /Part ratings/ });
  await expect(ratings.locator('.check.fail')).toContainText('Raspberry Pi 4 Model B · Pin voltage', { timeout: 15000 });
  await page.getByText('Board pinouts', { exact: true }).click();
  const header = page.getByRole('list', { name: 'Raspberry Pi 4 Model B header pins' });
  await expect(header.locator('.pin-used')).toContainText('GPIO17 · P1');
  await expect(header.getByRole('listitem')).toHaveCount(40);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('placing a board pin lets you choose board, header pin and mode', async ({ page }) => {
  await page.goto('/?mode=build');
  await page.getByRole('button', { name: 'Board pin', exact: true }).click();
  await page.getByRole('button', { name: 'Add to grid', exact: true }).click();
  await page.getByRole('button', { name: 'Select P1 GPIO17', exact: true }).click();
  await page.getByLabel(/^Board/).selectOption('raspberry_pi_5');
  await page.getByLabel(/^Header pin/).selectOption('12');
  await page.getByLabel(/^Mode/).selectOption('pulse');
  await expect(page.getByRole('button', { name: 'Select P1 GPIO18', exact: true })).toBeVisible();
  await expect(page.getByLabel('Pulse period (ms)')).toBeVisible();
  await page.getByLabel(/^Header pin/).selectOption('1');
  expect(await page.getByLabel(/^Mode/).locator('option').allTextContents()).toEqual(['Power supply']);
});

test('circuit library: insert a block beside the circuit, or open one and simulate it', async ({ page }) => {
  await page.goto('/?mode=build');
  await page.getByText(/^Circuit library/).click();
  await page.getByRole('button', { name: 'Insert LED on a Pi GPIO pin', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select P1 GPIO17', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Select R1 1 kΩ', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Select R2 330 Ω', exact: true })).toBeVisible();
  page.once('dialog', dialog => { void dialog.accept(); });
  await page.getByRole('button', { name: 'Open Relay or solenoid driver', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Select Q1 IRLZ44N', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Simulate circuit' }).click();
  await expect(page.getByRole('region', { name: /Part ratings/ })).toContainText('All 9 within limits', { timeout: 15000 });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
