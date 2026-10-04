import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import AxeBuilder from '@axe-core/playwright';

test('private save, explicit AI share, live edit, revision result, undo, conflict and revoke', async ({ page, request }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Build circuit', exact: true }).click();
  await expect(page.getByText('Private until you explicitly share.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Save new project', exact: true }).click();
  await expect(page.getByText('Project saved privately.', { exact: false })).toBeVisible();
  const projects = await (await request.get('/api/projects')).json();
  expect((await (await request.get('/api/projects/' + projects[0].id + '/grants')).json()).length).toBe(0);
  await page.getByRole('button', { name: 'Share this grid with my AI', exact: true }).click();
  await expect(page.getByText('Live workspace:', { exact: false })).toBeVisible();
  const workspaces = await (await request.get('/api/projects?kind=workspace')).json();
  const edit = (value: number) => execFileSync(resolve('../.venv/bin/python'), ['-m', 'deploy.project_browser_checks', workspaces[0].id, String(value)],
    { cwd: '..', env: process.env, encoding: 'utf8' });
  edit(2200);
  await expect(page.getByLabel('Custom value (SI units)')).toHaveValue('2200', { timeout: 10000 });
  await page.getByRole('button', { name: 'Run shared revision', exact: true }).click();
  await expect(page.getByText('Simulation complete. Paused for inspection.', { exact: false })).toBeVisible({ timeout: 15000 });
  await expect(page.getByLabel('Frame time')).toContainText('20 ms');
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect.poll(async () => (await (await request.get('/api/projects/' + workspaces[0].id + '/view')).json())).toBeNull();
  await page.getByLabel('Watch from (ms)').fill('10');
  await page.getByLabel('Watch until (ms)').fill('15');
  execFileSync(resolve('../.venv/bin/python'), ['-m', 'deploy.project_browser_checks', 'view', workspaces[0].id],
    { cwd: '..', env: process.env, encoding: 'utf8' });
  await expect(page.getByLabel('Frame time')).toContainText('20 ms');
  await expect(page.getByLabel('Watch from (ms)')).toHaveValue('0');
  await expect.poll(async () => (await (await request.get('/api/projects/' + workspaces[0].id + '/view')).json())).toBeNull();
  await page.getByRole('button', { name: 'Undo server change', exact: true }).click();
  await page.getByRole('button', { name: 'Select R1 1 kΩ', exact: true }).click();
  await expect(page.getByLabel('Custom value (SI units)')).toHaveValue('1000');
  await page.route('**/api/projects/' + workspaces[0].id, route => route.abort());
  await page.getByLabel('Custom value (SI units)').fill('4700');
  edit(3300);
  await page.unroute('**/api/projects/' + workspaces[0].id);
  await expect(page.getByText('Revision conflict.', { exact: false })).toBeVisible({ timeout: 10000 });
  await expect(page.getByLabel('Custom value (SI units)')).toHaveValue('4700');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Use server revision', exact: true }).click();
  await expect(page.getByLabel('Custom value (SI units)')).toHaveValue('3300');
  await page.getByRole('button', { name: 'Stop sharing', exact: true }).click();
  expect(() => edit(6800)).toThrow();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
