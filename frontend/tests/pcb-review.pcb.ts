import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

/** The real-worker fixture supplies this board and socket; never targets a hosted account. */
test('generate and re-import a KiCad board', async ({ page }) => {
  await page.goto('/workbench?mode=build');
  await expect(page.getByRole('heading', { name: 'PCB review' })).toBeVisible();
  await page.getByRole('button', { name: 'Generate board draft' }).click();
  await expect(page.getByText('Unrouted draft:', { exact: false })).toBeVisible({ timeout: 60000 });
  await expect(page.getByText('Unconnected:', { exact: false })).toBeVisible();
  await expect(page.getByRole('img', { name: 'PCB layer view' })).toBeVisible();
  await page.locator('.pcb-review').screenshot({ path: '/tmp/circuit-pcb-review.png' });
  await page.getByRole('combobox', { name: 'View' }).selectOption('back');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download KiCad board' }).click();
  const path = await (await download).path();
  expect(path).toBeTruthy();
  const board = await readFile(path!);
  expect(board.toString()).toContain('(kicad_pcb');
  await page.locator('.pcb-review input[type=file]').setInputFiles({ name: 'board.kicad_pcb', mimeType: 'text/plain', buffer: board });
  await expect(page.getByText('Imported KiCad board.', { exact: false })).toBeVisible({ timeout: 60000 });
  await page.locator('.pcb-review input[type=file]').setInputFiles('../tests/fixtures/pcb/partially-routed.kicad_pcb');
  await expect(page.getByText('Tracks and vias: 1', { exact: false })).toBeVisible({ timeout: 60000 });
  await expect(page.getByText('Imported KiCad board.', { exact: false })).toBeVisible({ timeout: 60000 });
  await page.getByText('Board components').click();
  await expect(page.locator('.pcb-review').getByText('U1 · LM7805', { exact: false })).toBeVisible();
  await page.getByLabel('Language').selectOption('de');
  await expect(page.getByRole('heading', { name: 'Platinenprüfung' })).toBeVisible();
});
