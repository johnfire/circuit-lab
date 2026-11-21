import { defineConfig } from '@playwright/test';

if (!process.env.CIRCUIT_PCB_SOCKET) throw new Error('Provide the isolated PCB worker socket');
export default defineConfig({
  testDir: './tests', testMatch: '**/*.pcb.ts', workers: 1, timeout: 120000,
  use: { baseURL: 'http://127.0.0.1:8014', headless: true },
  webServer: { command: '../.venv/bin/uvicorn backend.application:app --app-dir .. --host 127.0.0.1 --port 8014',
    url: 'http://127.0.0.1:8014/api/health', reuseExistingServer: false, timeout: 30000 },
});
